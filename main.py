import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re
import json
import html
from collections import Counter
from pandas.tseries.offsets import DateOffset
from PIL import Image, UnidentifiedImageError

from data_store import (
    DEFAULT_IMAGE,
    IMAGE_DIR,
    MONTH_MAP,
    MONTH_NAMES,
    TAGS_FILE,
    ensure_storage,
    load_data,
    new_card_id,
    update_data,
)

st.set_page_config(
    page_title="Card Tracker",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "A simple, local-first credit card tracker."
    }
)

# --- Configuration ---
# Define constant file paths and directory names.
# This makes it easy to change them in one place.
ensure_storage()

# --- App Constants ---
# Constants for date formatting and data schema
DATE_FORMATS = ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]
# Map user-friendly date formats to Python's strftime/strptime codes
STRFTIME_MAP = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY-MM-DD": "%Y-%m-%d"
}
# --- Initialize Session State ---
# Streamlit's session state is used to store variables across reruns.
# We use it here to manage which "page" is shown, what card is being
# edited, and other UI-related states.

# "Page" routing flags
if 'show_add_form' not in st.session_state:
    st.session_state.show_add_form = False # Show the "Add Card" page
if 'show_edit_form' not in st.session_state:
    st.session_state.show_edit_form = False # Show the "Edit Card" page
if 'show_sort_form' not in st.session_state:
    st.session_state.show_sort_form = False # Show the "Sort Order" page
if 'show_details_page' not in st.session_state:
    st.session_state.show_details_page = False # Show the "Card Details" page
if 'show_tag_manager' not in st.session_state:
    st.session_state.show_tag_manager = False # Show the "Manage Tags" page

# Data state for passing info between pages
if 'card_to_edit' not in st.session_state:
    st.session_state.card_to_edit = None # Stores the DataFrame *index* of the card to edit
if 'card_to_view' not in st.session_state:
    st.session_state.card_to_view = None # Stores the *index* of the card to view
if 'card_to_delete' not in st.session_state:
    st.session_state.card_to_delete = None # Stores the *index* for the 2-step cancel confirmation

# UI state for forms
if 'date_format' not in st.session_state:
    st.session_state.date_format = "DD/MM/YYYY" # User's preferred date format
if 'add_method' not in st.session_state:
    st.session_state.add_method = "Choose from list" # Toggle on the "Add Card" page
if 'card_to_add_selection' not in st.session_state:
    st.session_state.card_to_add_selection = None # The selected card from the dropdown
if 'duplicate_sort_numbers' not in st.session_state:
    st.session_state.duplicate_sort_numbers = [] # Used to show errors on the Sort page

# Session state for live image preview
# This is a common Streamlit pattern. We need to store the uploaded image
# in session state *before* the form is submitted to show a live preview.
if 'image_uploader_key' not in st.session_state:
    # We use a changing key to "reset" the file uploader widget
    st.session_state.image_uploader_key = str(datetime.now().timestamp())
if 'uploaded_image_preview' not in st.session_state:
    st.session_state.uploaded_image_preview = None # Stores the UploadedFile object

# =============================================================================
#  Helper Functions
# =============================================================================

def prettify_bank_name(bank_name):
    """Converts file-safe bank names (e.g., 'AmericanExpress') to display-friendly names."""
    if bank_name == "StandardChartered":
        return "Standard Chartered"
    if bank_name == "AmericanExpress":
        return "American Express"
    return bank_name


def get_card_mapping():
    """
    Scans the IMAGE_DIR for card images (png, jpg).
    It parses filenames like "BankName_Card_Name.png" into a dictionary:
    { "BankName Card Name": "BankName_Card_Name.png" }
    This dictionary populates the "Choose from list" dropdown.
    """
    card_mapping = {}
    try:
        for filename in os.listdir(IMAGE_DIR):
            if filename.endswith((".png", ".jpg", ".jpeg")) and filename != DEFAULT_IMAGE:
                base_name = os.path.splitext(filename)[0] # Remove extension
                parts = base_name.split("_")
                if len(parts) >= 2:
                    bank_raw = parts[0]
                    bank = prettify_bank_name(bank_raw) # Make name display-friendly
                    card_name = " ".join(parts[1:])
                    display_name = f"{bank} {card_name}"
                    card_mapping[display_name] = filename
    except FileNotFoundError:
        st.error(f"Image directory '{IMAGE_DIR}' not found. Please create it.")
    return card_mapping


def load_tags():
    """Loads the master list of tags from TAGS_FILE (tags.json)."""
    if not os.path.exists(TAGS_FILE):
        return []
    try:
        with open(TAGS_FILE, 'r') as f:
            tags = json.load(f)
            return sorted(list(set(tags))) # Return sorted, unique list
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_tags(tags_list):
    """Saves the master list of tags to TAGS_FILE (tags.json)."""
    # Clean tags: remove whitespace and ensure uniqueness and sort order
    unique_sorted_tags = sorted(list(set(t.strip() for t in tags_list if t.strip())))
    try:
        with open(TAGS_FILE, 'w') as f:
            json.dump(unique_sorted_tags, f, indent=4) # indent=4 for readability
        return True
    except Exception as e:
        st.error(f"Failed to save tags: {e}")
        return False


def save_uploaded_image(uploaded_file, bank, card_name):
    """Validate and persist an uploaded card image."""
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValueError("Image must be 5 MB or smaller.")

    try:
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc

    uploaded_file.seek(0)
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Image must be PNG or JPG.")

    bank_safe = re.sub(r'[^a-zA-Z0-9]', '', bank)
    card_safe = re.sub(r'[^a-zA-Z0-9]', '', card_name)
    image_filename = f"Custom_{bank_safe}_{card_safe}_{int(datetime.now().timestamp())}{extension}"
    save_path = os.path.join(IMAGE_DIR, image_filename)
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    uploaded_file.seek(0)
    return image_filename


def mutate_card(card_id, mutator):
    def apply_mutation(df):
        matches = df.index[df["Card ID"] == card_id].tolist()
        if matches:
            mutator(df, matches[0])
        return df

    return update_data(apply_mutation)


# =============================================================================
# 1. "Add New Card" Page (Main Area)
# =============================================================================
def show_add_card_form(card_mapping):
    """Displays the form for adding a new card."""
    st.title("Add a New Card", anchor=False)

    # This flag is used to reset the image preview when the page is first loaded
    if 'add_form_loaded' not in st.session_state:
        st.session_state.uploaded_image_preview = None
        st.session_state.add_form_loaded = True

    # This radio button controls the UI logic below
    st.radio(
        "How would you like to add a card?",
        ("Choose from list", "Add a custom card"),
        horizontal=True,
        key="add_method"
    )

    bank, card_name, image_filename = None, None, None

    if st.session_state.add_method == "Choose from list":
        # If user picks "Choose from list", show the dropdown
        st.session_state.uploaded_image_preview = None # Clear any custom image
        if not card_mapping:
            st.error("No pre-listed card images found in 'card_images' folder.")
            st.session_state.card_to_add_selection = None
        else:
            # Set a default selection to avoid errors
            if st.session_state.card_to_add_selection is None and card_mapping:
                st.session_state.card_to_add_selection = sorted(card_mapping.keys())[0]
            st.selectbox(
                "Choose a card*",
                options=sorted(card_mapping.keys()),
                key="card_to_add_selection"
            )
            # Show the image preview for the selected card
            if st.session_state.card_to_add_selection:
                image_filename = card_mapping[st.session_state.card_to_add_selection]
                st.image(os.path.join(IMAGE_DIR, image_filename))
    else:
        # If user picks "Add a custom card", show text inputs and file uploader
        st.info("Add your card details below. You can upload a custom image.")
        
        # --- Live Image Preview Logic ---
        # The file uploader is *outside* the form.
        uploaded_file = st.file_uploader(
            "Upload Card Image (Optional)", 
            type=["png", "jpg", "jpeg"],
            key=st.session_state.image_uploader_key # Use the resettable key
        )
        
        # When a file is uploaded, store it in session state
        if uploaded_file is not None:
            st.session_state.uploaded_image_preview = uploaded_file
        
        # Show either the newly uploaded image or the default
        if st.session_state.uploaded_image_preview is not None:
            st.image(st.session_state.uploaded_image_preview)
        else:
            st.image(os.path.join(IMAGE_DIR, DEFAULT_IMAGE))
    
    # --- The Main Form ---
    # All inputs for the new card are inside this form
    with st.form("new_card_form"):
        uploaded_file_in_form = None # This is a placeholder; we use session state now
        
        # These inputs only appear if "Add a custom card" is selected
        if st.session_state.add_method == "Add a custom card":
            st.subheader("Card Details", anchor=False)
            bank = st.text_input("Bank Name*")
            card_name = st.text_input("Card Name*")
            # The file uploader is *not* in the form, so we read it from state later
        
        st.divider()
        st.subheader("Enter Your Personal Details", anchor=False)
        last_4_digits = st.text_input(
            "Last 4 Digits (Optional)", 
            max_chars=4, 
            help="Useful for tracking supplementary cards."
        )
        st.write("Card Expiry*")
        col1, col2 = st.columns(2)
        with col1:
            expiry_mm = st.text_input("MM*", placeholder="05", max_chars=2, help="e.g., 05 for May")
        with col2:
            expiry_yy = st.text_input("YY*", placeholder="27", max_chars=2, help="e.g., 27 for 2027")
        annual_fee = st.number_input("Annual Fee ($)", min_value=0.0, step=1.00, format="%.2f")

        # Load the master tag list for the multiselect options
        all_tags = load_tags()
        selected_tags = st.multiselect("Tags", options=all_tags)

        st.subheader("Notes", anchor=False)
        notes = st.text_area("Add any notes for this card (e.g., waiver info, benefits).")

        st.divider()
        st.subheader("Welcome Offer Tracking (Optional)", anchor=False)
        bonus_offer = st.text_input("Bonus Offer", placeholder="e.g., 50,000 miles or $200 cashback")
        min_spend = st.number_input("Min Spend Required ($)", min_value=0.0, step=100.0, format="%.2f")
        min_spend_deadline = st.date_input("Min Spend Deadline", value=None, format=st.session_state.date_format)
        bonus_status = st.selectbox(
            "Bonus Status",
            ("Not Started", "In Progress", "Met", "Received"), index=0,
            help="Set this to 'Met' or 'Received' when you're done!"
        )

        st.write("---")
        st.subheader("Optional Dates", anchor=False)
        st.caption("You can leave these blank. To clear a set date, click the 'x' in the date widget.")
        applied_date = st.date_input("Date Applied", value=None, format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=None, format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=None, format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=None, format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=None, format=st.session_state.date_format)

        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Add This Card", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                # On Cancel:
                st.session_state.show_add_form = False # Go back to dashboard
                st.session_state.uploaded_image_preview = None # Clear image preview
                # Reset the uploader key to fully clear the widget
                st.session_state.image_uploader_key = str(datetime.now().timestamp())
                st.rerun()

    # --- Form Submission Logic ---
    # This code runs *only* after the "Add This Card" button is clicked
    if submitted:
        # 1. Determine Bank, Card Name, and Image Filename
        if st.session_state.add_method == "Choose from list":
            if not st.session_state.card_to_add_selection:
                st.error("Please select a card from the list."); return
            # Parse bank/card name from the selected image filename
            image_filename = card_mapping[st.session_state.card_to_add_selection]
            base_name = os.path.splitext(image_filename)[0]
            parts = base_name.split("_")
            bank_raw = parts[0]
            bank = prettify_bank_name(bank_raw)
            card_name = " ".join(parts[1:])
        else:
            # Get bank/card name from text inputs
            if not bank or not card_name:
                st.error("Bank Name and Card Name are required for custom cards."); return
            
            # 2. Handle Custom Image Upload
            image_filename = DEFAULT_IMAGE # Default, in case no file was uploaded
            uploaded_file = st.session_state.uploaded_image_preview # Get file from state
            
            if uploaded_file is not None:
                try:
                    image_filename = save_uploaded_image(uploaded_file, bank, card_name)
                except ValueError as e:
                    st.error(f"Error saving image: {e}")
                    return

        # 3. Validation
        # Use regex to validate expiry and last 4 digits
        month_match = re.match(r"^(0[1-9]|1[0-2])$", expiry_mm)
        if not month_match: st.error("Expiry MM must be a valid month (e.g., 01, 05, 12)."); return
        year_match = re.match(r"^\d{2}$", expiry_yy)
        if not year_match: st.error("Expiry YY must be two digits (e.g., 25, 27)."); return
        if last_4_digits and not re.match(r"^\d{4}$", last_4_digits):
            st.error("Last 4 Digits must be exactly 4 numbers (e.g., 1234)."); return

        # 4. Data Preparation
        card_expiry_mm_yy = f"{expiry_mm}/{expiry_yy}"
        fee_month = MONTH_MAP.get(expiry_mm) # '05' -> 'May'

        # 5. Create New Card Record
        # Build a dictionary for the new card
        new_card = {
            "Card ID": new_card_id(),
            "Bank": bank, "Card Name": card_name, "Annual Fee": annual_fee,
            "Card Expiry (MM/YY)": card_expiry_mm_yy, "Month of Annual Fee": fee_month,
            "Image Filename": image_filename,
            "Date Applied": pd.to_datetime(applied_date),
            "Date Approved": pd.to_datetime(approved_date),
            "Date Received Card": pd.to_datetime(received_date),
            "Date Activated Card": pd.to_datetime(activated_date),
            "First Charge Date": pd.to_datetime(first_charge_date),
            "Sort Order": new_sort_order,
            "Notes": notes,
            "Cancellation Date": pd.NaT, # New cards are not cancelled
            "Re-apply Date": pd.NaT,
            "Tags": ",".join(selected_tags), # Store list as a comma-separated string
            "Bonus Offer": bonus_offer,
            "Min Spend": min_spend,
            "Min Spend Deadline": pd.to_datetime(min_spend_deadline),
            "Bonus Status": bonus_status,
            "Last 4 Digits": last_4_digits,
            "Current Spend": 0.0, # New cards start at 0 spend
            "FeeWaivedCount": 0,
            "FeePaidCount": 0,
            "LastFeeActionYear": 0,
            "LastFeeAction": ""
        }

        def add_card(df):
            max_sort = df['Sort Order'].max()
            new_card["Sort Order"] = 1 if pd.isna(max_sort) or max_sort < 1 else int(max_sort + 1)
            return pd.concat([df, pd.DataFrame([new_card])], ignore_index=True)

        update_data(add_card)

        # 7. Reset State and Rerun
        st.success(f"Successfully added {bank} {card_name}!")
        st.session_state.show_add_form = False # Go back to dashboard
        st.session_state.uploaded_image_preview = None # Clear image
        st.session_state.image_uploader_key = str(datetime.now().timestamp()) # Reset key
        st.rerun()


# =============================================================================
# 2. "Edit Card" Page
# =============================================================================
def show_edit_form():
    """Displays the form for editing an existing card."""
    st.title("Edit Card Details", anchor=False)
    all_cards_df = load_data()
    
    # Get the index of the card to edit from session state
    card_id = st.session_state.card_to_edit
    matches = all_cards_df.index[all_cards_df["Card ID"] == card_id].tolist()
    
    # Safety check: if the index is invalid, go back to the dashboard
    if card_id is None or not matches:
        st.error("Could not find card to edit. Returning to dashboard."); st.session_state.show_edit_form = False; st.rerun(); return
    card_index = matches[0]
    
    # Get the row (as a Series) for the card we are editing
    card_data = all_cards_df.loc[card_index]

    # Reset image preview when page loads
    if 'edit_form_loaded' not in st.session_state:
        st.session_state.uploaded_image_preview = None
        st.session_state.edit_form_loaded = True
    
    # Pre-fill expiry month/year from the saved "MM/YY" string
    try:
        default_mm, default_yy = card_data["Card Expiry (MM/YY)"].split('/')
    except (ValueError, AttributeError):
        default_mm, default_yy = "", "" # Handle blank/invalid data

    st.subheader(f"Editing: {card_data['Bank']} {card_data['Card Name']}", anchor=False)
    st.caption("Note: You cannot change the manual sort order here.")
    
    # File uploader and preview OUTSIDE form
    # Same pattern as the "Add Card" page for live image preview
    uploaded_file = st.file_uploader(
        "Change Card Image (Optional)", 
        type=["png", "jpg", "jpeg"],
        key=st.session_state.image_uploader_key # Use a key that we can reset
    )
    
    if uploaded_file is not None:
        st.session_state.uploaded_image_preview = uploaded_file
    
    if st.session_state.uploaded_image_preview is not None:
        # Show the new preview
        st.image(st.session_state.uploaded_image_preview)
    else:
        # Show the card's *current* image
        current_image_path = os.path.join(IMAGE_DIR, str(card_data["Image Filename"]))
        if not os.path.exists(current_image_path): 
            current_image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
        st.image(current_image_path)

    # --- The Edit Form ---
    # All inputs are pre-filled with the card's existing data
    with st.form("edit_card_form"):
        bank = st.text_input("Bank Name*", value=card_data["Bank"])
        card_name = st.text_input("Card Name*", value=card_data["Card Name"])
        st.divider()
        st.subheader("Edit Personal Details", anchor=False)

        last_4_digits = st.text_input(
            "Last 4 Digits (Optional)", 
            value=card_data.get("Last 4 Digits", ""), # .get() avoids error if column is new
            max_chars=4, 
            help="Useful for tracking supplementary cards."
        )
        st.write("Card Expiry*")
        col1, col2 = st.columns(2)
        with col1:
            expiry_mm = st.text_input("MM*", value=default_mm, max_chars=2, help="e.g., 05 for May")
        with col2:
            expiry_yy = st.text_input("YY*", value=default_yy, max_chars=2, help="e.g., 27 for 2027")

        annual_fee = st.number_input("Annual Fee ($)", min_value=0.0, step=1.00, format="%.2f", value=card_data["Annual Fee"])
        
        # --- FIX: Combine default tags into options list to prevent crash ---
        all_tags = load_tags()
        default_tags_str = card_data.get("Tags", "")
        default_tags = [t.strip() for t in default_tags_str.split(',') if t.strip()]
        combined_options = sorted(list(set(all_tags + default_tags)))
        selected_tags = st.multiselect("Tags", options=combined_options, default=default_tags)
        # ------------------------------------------------------------------

        st.subheader("Notes", anchor=False)
        notes = st.text_area("Card notes", value=card_data.get("Notes", ""))
        
        st.divider()
        st.subheader("Welcome Offer Tracking", anchor=False)
        bonus_offer = st.text_input("Bonus Offer", value=card_data.get("Bonus Offer", ""))
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            min_spend = st.number_input("Min Spend Required ($)", min_value=0.0, step=100.0, format="%.2f", value=card_data.get("Min Spend", 0.0))
        with b_col2:
            # Allow editing of 'Current Spend' here, not just on the dashboard
            current_spend = st.number_input("Current Spend ($)", min_value=0.0, step=100.0, format="%.2f", value=card_data.get("Current Spend", 0.0))
        
        # Helper function to convert date values for the st.date_input
        # It returns None if the date is NaT, which st.date_input requires.
        def get_date(date_val):
            return pd.to_datetime(date_val) if pd.notna(date_val) else None
        
        min_spend_deadline = st.date_input("Min Spend Deadline", value=get_date(card_data.get("Min Spend Deadline")), format=st.session_state.date_format)
        
        # Find the index of the current status to set the selectbox default
        status_options = ["Not Started", "In Progress", "Met", "Received"]
        default_status = card_data.get("Bonus Status", "Not Started")
        status_index = status_options.index(default_status) if default_status in status_options else 0
        bonus_status = st.selectbox("Bonus Status", status_options, index=status_index)
        
        st.write("---")
        st.subheader("Edit Optional Dates", anchor=False)
        applied_date = st.date_input("Date Applied", value=get_date(card_data["Date Applied"]), format=st.session_state.date_format)
        approved_date = st.date_input("Date Approved", value=get_date(card_data["Date Approved"]), format=st.session_state.date_format)
        received_date = st.date_input("Date Received Card", value=get_date(card_data["Date Received Card"]), format=st.session_state.date_format)
        activated_date = st.date_input("Date Activated Card", value=get_date(card_data["Date Activated Card"]), format=st.session_state.date_format)
        first_charge_date = st.date_input("First Charge Date", value=get_date(card_data["First Charge Date"]), format=st.session_state.date_format)
        
        st.caption("Cancellation and Re-apply dates are handled via the 'Cancel Card' button on the dashboard.")

        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Save Changes", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                # On Cancel:
                st.session_state.show_edit_form = False; st.session_state.card_to_edit = None
                st.session_state.uploaded_image_preview = None # Clear preview
                st.session_state.image_uploader_key = str(datetime.now().timestamp()) # Reset key
                st.rerun()

    # --- Form Submission Logic ---
    if submitted:
        # 1. Validation
        if not bank or not card_name: st.error("Bank Name and Card Name are required."); return
        month_match = re.match(r"^(0[1-9]|1[0-2])$", expiry_mm); 
        if not month_match: st.error("Expiry MM must be a valid month (e.g., 01, 05, 12)."); return
        year_match = re.match(r"^\d{2}$", expiry_yy); 
        if not year_match: st.error("Expiry YY must be two digits (e.g., 25, 27)."); return
        if last_4_digits and not re.match(r"^\d{4}$", last_4_digits):
            st.error("Last 4 Digits must be exactly 4 numbers (e.g., 1234)."); return
        
        # 2. Image Upload Logic for Edit
        # By default, keep the card's *old* image filename
        new_image_filename = card_data["Image Filename"] 
        uploaded_file = st.session_state.uploaded_image_preview # Check if a new file was added
        
        if uploaded_file is not None:
            try:
                new_image_filename = save_uploaded_image(uploaded_file, bank, card_name)
            except ValueError as e:
                st.error(f"Error saving image: {e}")
                return
            # Note: We don't delete the old image, to be safe.
        
        card_expiry_mm_yy = f"{expiry_mm}/{expiry_yy}"
        fee_month = MONTH_MAP.get(expiry_mm)

        card_id = card_data["Card ID"]

        def update_card(df):
            matches = df.index[df["Card ID"] == card_id].tolist()
            if not matches:
                return df
            idx = matches[0]
            df.loc[idx, "Bank"] = bank
            df.loc[idx, "Card Name"] = card_name
            df.loc[idx, "Image Filename"] = new_image_filename
            df.loc[idx, "Annual Fee"] = annual_fee
            df.loc[idx, "Card Expiry (MM/YY)"] = card_expiry_mm_yy
            df.loc[idx, "Month of Annual Fee"] = fee_month
            df.loc[idx, "Date Applied"] = pd.to_datetime(applied_date)
            df.loc[idx, "Date Approved"] = pd.to_datetime(approved_date)
            df.loc[idx, "Date Received Card"] = pd.to_datetime(received_date)
            df.loc[idx, "Date Activated Card"] = pd.to_datetime(activated_date)
            df.loc[idx, "First Charge Date"] = pd.to_datetime(first_charge_date)
            df.loc[idx, "Notes"] = notes
            df.loc[idx, "Tags"] = ",".join(selected_tags)
            df.loc[idx, "Bonus Offer"] = bonus_offer
            df.loc[idx, "Min Spend"] = min_spend
            df.loc[idx, "Min Spend Deadline"] = pd.to_datetime(min_spend_deadline)
            df.loc[idx, "Bonus Status"] = bonus_status
            df.loc[idx, "Last 4 Digits"] = last_4_digits
            df.loc[idx, "Current Spend"] = current_spend
            return df

        update_data(update_card)

        st.success(f"Successfully updated {bank} {card_name}!"); 
        st.session_state.show_edit_form = False; st.session_state.card_to_edit = None
        st.session_state.uploaded_image_preview = None # Clear preview
        st.session_state.image_uploader_key = str(datetime.now().timestamp()) # Reset key
        st.rerun()


# =============================================================================
# 3. Main Dashboard Page
# =============================================================================
def show_dashboard(all_cards_df, show_cancelled):
    """
    Displays the main dashboard, including summaries, trackers, and the card list.
    
    Args:
        all_cards_df (pd.DataFrame): The complete DataFrame of all cards.
        show_cancelled (bool): A flag from the sidebar, True if we should
                               include cancelled cards in the list.
    """
    
    # --- Main Page ---
    st.title("💳 Credit Card Dashboard", anchor=False)

    # Get date info for "due this/next month" logic
    today_dt = pd.to_datetime(datetime.today())
    current_month_index = today_dt.month - 1 # 0 = Jan, 1 = Feb...
    next_month_index = (current_month_index + 1) % 12 # Handle December
    current_month_name = MONTH_NAMES[current_month_index]
    next_month_name = MONTH_NAMES[next_month_index]
    
    current_year = today_dt.year # Get current year for fee tracking

    # Filter the DataFrame based on the "Show Cancelled" checkbox
    if show_cancelled:
        cards_to_display_df = all_cards_df.copy()
        st.info("Showing all cards, including cancelled.")
    else:
        # Keep only cards where 'Cancellation Date' is NaT (null)
        cards_to_display_df = all_cards_df[pd.isna(all_cards_df['Cancellation Date'])].copy()

    # --- Summary Metrics ---
    st.header("Summary", anchor=False)
    
    # Helper to convert "MonthName" to an index (0-11)
    def get_month_index(month_name):
        try: return MONTH_NAMES.index(month_name)
        except (ValueError, TypeError): return -1
            
    # Create a new column for the month index (0-11) for sorting/filtering
    cards_to_display_df['due_month_index'] = cards_to_display_df['Month of Annual Fee'].apply(get_month_index)
    
    # Calculate fees due *this* calendar year (from this month onward)
    cards_due_this_year_df = cards_to_display_df[cards_to_display_df['due_month_index'] >= current_month_index]
    count_due_this_year = len(cards_due_this_year_df)
    amount_due_this_year = cards_due_this_year_df['Annual Fee'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cards (Active)" if not show_cancelled else "Total Cards (All)", len(cards_to_display_df))
    col2.metric("Total Annual Fees", f"${cards_to_display_df['Annual Fee'].sum():,.2f}")
    col3.metric("Fees Due This Year (#)", count_due_this_year)
    col4.metric("Fees Due This Year ($)", f"${amount_due_this_year:,.2f}")
    st.divider()

    # --- Welcome Bonus Tracker ---
    st.header("Welcome Bonus Tracker", anchor=False)
    st.caption("Shows active bonuses with a status of 'Not Started' or 'In Progress'.")
    
    # Filter for cards that have a deadline AND are not yet 'Met' or 'Received'
    active_bonuses_df = cards_to_display_df[
        (pd.notna(cards_to_display_df['Min Spend Deadline'])) &
        (cards_to_display_df['Bonus Status'].isin(['Not Started', 'In Progress']))
    ].copy()

    # Calculate 'Days Left' and filter out expired bonuses
    active_bonuses_df['Days Left'] = (active_bonuses_df['Min Spend Deadline'] - today_dt).dt.days
    active_bonuses_df = active_bonuses_df[active_bonuses_df['Days Left'] >= 0]
    
    if active_bonuses_df.empty:
        st.write("No active minimum spend deadlines to track.")
    else:
        # Sort by soonest deadline first
        active_bonuses_df = active_bonuses_df.sort_values(by='Days Left')
        
        # Loop through each active bonus and display its status
        for index, card in active_bonuses_df.iterrows():
            days_left = card['Days Left']
            card_name_full = f"{card['Bank']} {card['Card Name']}"
            card_name_bold = f"**{card_name_full}**"
            deadline_str = card['Min Spend Deadline'].strftime('%d %b %Y')
            
            min_spend = card['Min Spend']
            current_spend = card['Current Spend']
            remaining_spend = max(0.0, min_spend - current_spend)
            progress_pct = 0.0
            if min_spend > 0:
                progress_pct = min(1.0, current_spend / min_spend)
            
            remaining_str = f"**${remaining_spend:,.0f} more**"
            
            # --- State 1: Spend is Met ---
            if current_spend >= min_spend and min_spend > 0:
                st.success(f"🎉 {card_name_bold}: You've hit the minimum spend!")
                st.progress(1.0, text=f"${current_spend:,.0f} / ${min_spend:,.0f} spent")
                
                # Show a button to change status to "Met"
                if st.button(f"Mark Bonus as 'Met'", key=f"mark_met_{index}", use_container_width=True):
                    def mark_bonus_met(df, idx):
                        df.loc[idx, "Bonus Status"] = "Met"

                    mutate_card(card["Card ID"], mark_bonus_met)
                    st.rerun() # Rerun to remove this card from the tracker
            
            # --- State 2: Spend is Not Met ---
            else:
                if days_left <= 30: # Show warning if < 30 days
                    st.warning(f"{card_name_bold}: **{days_left} days left** to spend {remaining_str}! (Deadline: {deadline_str})")
                else: # Show info otherwise
                    st.info(f"{card_name_bold}: {days_left} days left to spend {remaining_str}. (Deadline: {deadline_str})")
                
                # Show progress bar
                st.progress(progress_pct, text=f"${current_spend:,.0f} / ${min_spend:,.0f} spent")
                
                # --- Mini-form to update spend ---
                # Each card gets its own form
                with st.form(key=f"update_spend_{index}"):
                    st.caption("Update your total spend:")
                    f_col1, f_col2 = st.columns([3, 1])
                    with f_col1:
                        new_spend = st.number_input(
                            "Update Total Spend ($)",
                            min_value=0.0,
                            value=float(current_spend),
                            step=50.0,
                            label_visibility="collapsed"
                        )
                    with f_col2:
                        updated = st.form_submit_button("Update", use_container_width=True)
                    
                    if updated:
                        def update_spend(df, idx):
                            if df.loc[idx, "Bonus Status"] == "Not Started" and new_spend > 0:
                                df.loc[idx, "Bonus Status"] = "In Progress"
                            df.loc[idx, "Current Spend"] = new_spend

                        mutate_card(card["Card ID"], update_spend)
                        st.toast(f"Updated spend for {card_name_full}!")
                        st.rerun() 
            st.write("") # Add blank line
            
    st.divider()

    # --- Annual Fee Notifications ---
    st.header("Annual Fee Notifications", anchor=False)
    # Filter for cards due this month and next month
    cards_due_this_month = cards_to_display_df[cards_to_display_df["Month of Annual Fee"] == current_month_name]
    cards_due_next_month = cards_to_display_df[cards_to_display_df["Month of Annual Fee"] == next_month_name]
    
    st.subheader(f"Due This Month ({current_month_name})", anchor=False)
    if cards_due_this_month.empty: 
        st.info("No annual fees due this month.")
    else:
        # Loop over cards due this month
        for index, card_data in cards_due_this_month.iterrows():
            card_name_full = f"{card_data['Bank']} {card_data['Card Name']}"
            fee = card_data['Annual Fee']
            fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "Fee is $0, but please verify."

            # Check if action has already been taken this year
            if card_data['LastFeeActionYear'] == current_year:
                # If YES, show a green success message with the specific action
                action_taken = card_data.get("LastFeeAction")
                
                # This block handles data saved by older code.
                # If LastFeeAction is blank, we guess based on counts.
                if not action_taken:
                    if card_data.get("FeeWaivedCount", 0) > card_data.get("FeePaidCount", 0):
                            action_taken = "Waived"
                    else:
                            action_taken = "Paid" # Default to paid 
                
                st.success(f"✅ *{action_taken} Annual Fee for {card_name_full} for {current_year}.*")
            
            else:
                # If NO, show the red error message and the action buttons
                st.error(f"**{card_name_full}**: {fee_text}")
                
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("I Waived This Fee", key=f"waived_{index}", use_container_width=True):
                        def waive_fee(df, idx):
                            df.loc[idx, "FeeWaivedCount"] = df.loc[idx, "FeeWaivedCount"] + 1
                            df.loc[idx, "LastFeeActionYear"] = current_year
                            df.loc[idx, "LastFeeAction"] = "Waived"

                        mutate_card(card_data["Card ID"], waive_fee)
                        st.rerun()
                with b_col2:
                    if st.button("I Paid This Fee", key=f"paid_{index}", use_container_width=True):
                        def pay_fee(df, idx):
                            df.loc[idx, "FeePaidCount"] = df.loc[idx, "FeePaidCount"] + 1
                            df.loc[idx, "LastFeeActionYear"] = current_year
                            df.loc[idx, "LastFeeAction"] = "Paid"

                        mutate_card(card_data["Card ID"], pay_fee)
                        st.rerun()
            
            st.write("") 

    st.subheader(f"Due Next Month ({next_month_name})", anchor=False)
    if cards_due_next_month.empty: 
        st.info("No annual fees due next month.")
    else:
        # This section just shows a simple warning, no action buttons
        for _, card_data in cards_due_next_month.iterrows():
            fee = card_data['Annual Fee']; fee_text = f"The fee is **${fee:.2f}**." if fee > 0 else "Fee is $0, but please verify."
            st.warning(f"**{card_data['Bank']} {card_data['Card Name']}**: {fee_text}")
    st.divider()

    # --- Re-application Notifications ---
    st.header("Re-application Notifications", anchor=False)
    st.caption("Shows cards that were cancelled and are now (or soon) eligible to re-apply for a new bonus.")
    
    # Filter for cards that have a Re-apply Date set
    reapply_df = all_cards_df[pd.notna(all_cards_df['Re-apply Date'])].copy()
    # Filter for dates that are within the next 60 days (or are in the past)
    eligible_cards = reapply_df[
        (reapply_df['Re-apply Date'] <= today_dt + pd.DateOffset(days=60))
    ].sort_values(by='Re-apply Date')
    
    if eligible_cards.empty:
        st.write("No cards are eligible for re-application soon.")
    else:
        for _, card in eligible_cards.iterrows():
            card_name = f"{card['Bank']} {card['Card Name']}"
            reapply_date_str = card['Re-apply Date'].strftime('%d %b %Y')
            
            # If the date is in the past, show success
            if card['Re-apply Date'] <= today_dt:
                st.success(f"**{card_name}**: You are **now eligible** to re-apply! (Eligible since {reapply_date_str})")
            # If the date is in the future, show info
            else:
                days_until = (card['Re-apply Date'] - today_dt).days
                st.info(f"**{card_name}**: Eligible to re-apply in **{days_until} days**. (On {reapply_date_str})")
    st.divider()

    # --- "All My Cards" List ---
    st.header("All My Cards", anchor=False)
    
    # This is a key calculation for "Sort by Due Date".
    # It creates a 'due_sort_key' that wraps around, so if the
    # current month is November (10), December (11) gets key 1,
    # and January (0) gets key 2. ( (0 - 10 + 12) % 12 = 2 )
    cards_to_display_df['due_sort_key'] = (cards_to_display_df['due_month_index'] - current_month_index + 12) % 12

    # --- Filters and Sort ---
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        bank_options = sorted(cards_to_display_df['Bank'].unique())
        selected_banks = st.multiselect("Filter by Bank", options=bank_options)
    with f_col2:
        tag_options = load_tags()
        selected_tags = st.multiselect("Filter by Tag", options=tag_options)
    with f_col3:
        sort_options = {
            "Manual (Custom Order)": "Sort Order",
            "Due Date (Soonest First)": "due_sort_key",
            "Annual Fee (High to Low)": "Annual Fee_desc",
            "Annual Fee (Low to High)": "Annual Fee_asc",
        }
        selected_sort_key = st.selectbox("Sort by", options=sort_options.keys())
        if sort_options[selected_sort_key] == "Sort Order":
            # Show the "Edit Manual Order" button only if sorting by it
            if st.button("Edit Manual Order", use_container_width=True):
                st.session_state.show_sort_form = True
                st.session_state.duplicate_sort_numbers = [] 
                st.rerun() # Go to the Sort page
    
    # --- Apply Filters ---
    cards_to_show_df_sorted = cards_to_display_df.copy()
    if selected_banks:
        # Filter DataFrame to rows where 'Bank' is in the selected list
        cards_to_show_df_sorted = cards_to_show_df_sorted[cards_to_show_df_sorted['Bank'].isin(selected_banks)]
    if selected_tags:
        # This logic handles multi-tag filtering
        def check_tags(card_tags_str):
            card_tags = set(t.strip() for t in card_tags_str.split(','))
            # 'all' means the card must have *every* tag in selected_tags
            return all(tag in card_tags for tag in selected_tags)
        
        cards_to_show_df_sorted = cards_to_show_df_sorted[
            cards_to_show_df_sorted['Tags'].apply(check_tags)
        ]

    # --- Apply Sort ---
    sort_logic = sort_options[selected_sort_key]
    if sort_logic == "Annual Fee_desc":
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="Annual Fee", ascending=False)
    elif sort_logic == "Annual Fee_asc":
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="Annual Fee", ascending=True)
    elif sort_logic == "due_sort_key":
        # Sort by our calculated 'due_sort_key'
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="due_sort_key", ascending=True)
    else: # Default: "Sort Order"
        cards_to_show_df_sorted = cards_to_show_df_sorted.sort_values(by="Sort Order", ascending=True)

    # Get the Python strftime code for the user's selected date format
    strftime_code = STRFTIME_MAP[st.session_state.date_format]
    
    if cards_to_show_df_sorted.empty:
        st.info("No cards match your current filters.")

    # Helper function to format dates for display, handling NaT (null) values
    def format_date_display(date_val):
        """Formats a date for display, returning an empty string if null."""
        if pd.isna(date_val):
            return ""
        return pd.to_datetime(date_val).strftime(strftime_code)

    # --- Main Card Loop ---
    # This loops through the final, filtered, and sorted DataFrame
    # and displays one card at a time.
    for index, card_row in cards_to_show_df_sorted.iterrows():
        st.divider()
        col1, col2 = st.columns([1, 3])

        with col1: # Image column
            image_path = os.path.join(IMAGE_DIR, str(card_row["Image Filename"]))
            if not os.path.exists(image_path): 
                image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
            if os.path.exists(image_path): 
                st.image(image_path)
            else: 
                st.caption("No Image")

        with col2: # Info column
            
            # --- Title/Expiry UI ---
            title_text = html.escape(f"{card_row['Bank']} {card_row['Card Name']}")
            last_4 = card_row.get("Last 4 Digits", "")
            if last_4:
                title_text += f" ({html.escape(str(last_4))})" # Add (1234) if it exists
            expiry_text = f"<b>Card Expiry:</b> {card_row['Card Expiry (MM/YY)']}"
            
            # This custom HTML places the Title on the left and Expiry on the right
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: -10px;">
                    <h3 style="margin-bottom: 0px;">{title_text}</h3>
                    <span style="opacity: 0.8; white-space: nowrap;">{expiry_text}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            is_cancelled = pd.notna(card_row["Cancellation Date"])
            
            if is_cancelled:
                # --- Cancelled Card View ---
                st.error("Status: Cancelled")
                c_col1, c_col2 = st.columns(2)
                with c_col1:
                    st.metric("Cancelled On", pd.to_datetime(card_row["Cancellation Date"]).strftime("%d %b %Y"))
                with c_col2:
                    st.metric("Re-apply After", pd.to_datetime(card_row["Re-apply Date"]).strftime("%d %b %Y"))
            else:
                # --- Active Card View ---
                st.metric(label="Annual Fee", value=f"${card_row['Annual Fee']:.2f}")

            # --- Due date status ---
            due_month_name = card_row['Month of Annual Fee']
            due_month_index = card_row['due_month_index'] 
            if not is_cancelled:
                if due_month_index == current_month_index:
                    st.error(f"❗ **Due this month** ({due_month_name})")
                elif due_month_index == next_month_index:
                    st.warning(f"⚠️ **Due next month** ({due_month_name})")
                elif due_month_index != -1:
                    st.info(f"✅ Due in {due_month_name}")
                else:
                    st.info(f"Due in {due_month_name}") # Fallback
            
            # Display tags if they exist
            tags_str = card_row.get("Tags", "")
            if tags_str:
                st.markdown(f"**Tags:** `{tags_str.replace(',', ', ')}`")

            # Display notes if they exist
            notes = card_row.get("Notes", "")
            if notes and pd.notna(notes):
                st.markdown("**Notes:**")
                st.text(str(notes))

            # --- Button Bar ---
            st.write("")  # Spacer
            
            # <--- LAYOUT FIX: Use equal widths and container_width=True
            b_col1, b_col2, b_col3, b_col4 = st.columns([1, 1, 1, 1])
            
            with b_col1: # Details button
                if st.button("Details", key=f"details_{index}", use_container_width=True):
                    # "Go" to the details page by setting its flag and the card index
                    st.session_state.card_to_view = card_row["Card ID"]; st.session_state.show_details_page = True; st.session_state.card_to_edit = None; st.session_state.card_to_delete = None; st.rerun()
            
            with b_col2: # Edit button
                if st.button("Edit", key=f"edit_{index}", use_container_width=True):
                    # "Go" to the edit page
                    st.session_state.card_to_edit = card_row["Card ID"]; st.session_state.show_edit_form = True; st.session_state.card_to_delete = None
                    st.session_state.edit_form_loaded = False # Reset edit form preview
                    st.rerun()
            
            with b_col3: # Cancel/Re-activate button
                if is_cancelled:
                    # --- Re-activate Button ---
                    if st.button("Re-activate", key=f"reactivate_{index}", use_container_width=True):
                        def reactivate(df, idx):
                            df.loc[idx, "Cancellation Date"] = pd.NaT
                            df.loc[idx, "Re-apply Date"] = pd.NaT
                            df.loc[idx, "LastFeeActionYear"] = 0
                            df.loc[idx, "LastFeeAction"] = ""

                        mutate_card(card_row["Card ID"], reactivate)
                        st.success(f"Re-activated {card_row['Bank']} {card_row['Card Name']}.")
                        st.rerun()
                else:
                    # --- Cancel Button (2-step) ---
                    # Step 1: User clicks "Cancel Card"
                    # We set 'card_to_delete' to this card's index
                    if st.session_state.card_to_delete == card_row["Card ID"]:
                        # Step 2: The page reruns, and now this block is active
                        # Show the confirmation buttons
                        if st.button("Confirm Cancel", key=f"confirm_cancel_{index}", type="primary", use_container_width=True):
                            cancel_date = pd.to_datetime('today')
                            # Set re-apply to 13 months from now (a safe buffer)
                            reapply_date = cancel_date + DateOffset(months=13)

                            def cancel_card(df, idx):
                                df.loc[idx, "Cancellation Date"] = cancel_date
                                df.loc[idx, "Re-apply Date"] = reapply_date

                            mutate_card(card_row["Card ID"], cancel_card)
                            st.session_state.card_to_delete = None # Clear state
                            st.success(f"Cancelled {card_row['Bank']} {card_row['Card Name']}.")
                            st.rerun()
                        if st.button("Cancel Action", key=f"cancel_cancel_{index}", use_container_width=True):
                            st.session_state.card_to_delete = None; st.rerun() # Clear state
                    else:
                        # Step 1: Show the initial "Cancel Card" button
                        if st.button("Cancel Card", key=f"cancel_{index}", use_container_width=True):
                            st.session_state.card_to_delete = card_row["Card ID"]; st.session_state.card_to_edit = None; st.rerun()
            
            with b_col4: # Delete button (2-step)
                # This uses a *different* session state key per card for confirmation
                if st.session_state.get(f"confirm_permanent_delete_{index}", False):
                    # Step 2: Show confirmation buttons
                    if st.button("CONFIRM DELETE", key=f"confirm_delete_permanent_{index}", type="primary", use_container_width=True):
                        def delete_card(df):
                            return df[df["Card ID"] != card_row["Card ID"]].reset_index(drop=True)

                        update_data(delete_card)
                        st.session_state[f"confirm_permanent_delete_{index}"] = False 
                        st.success(f"Permanently deleted {card_row['Bank']} {card_row['Card Name']}.")
                        st.rerun()
                    if st.button("No, Keep Card", key=f"cancel_delete_permanent_{index}", use_container_width=True):
                        st.session_state[f"confirm_permanent_delete_{index}"] = False 
                        st.rerun()
                else:
                    # Step 1: Show initial "Delete" button
                    if st.button("Delete Permanently", key=f"delete_permanent_{index}", use_container_width=True):
                        st.session_state[f"confirm_permanent_delete_{index}"] = True 
                        st.session_state.card_to_edit = None # Clear other states
                        st.session_state.card_to_delete = None 
                        st.rerun()

            # --- Expander for Other Dates ---
            with st.expander("Show All Dates and Details"):
                d_col1, d_col2, d_col3 = st.columns(3)
                with d_col1:
                    st.metric("Date Applied", format_date_display(card_row["Date Applied"]))
                    st.metric("Date Approved", format_date_display(card_row["Date Approved"]))
                with d_col2:
                    st.metric("Date Received", format_date_display(card_row["Date Received Card"]))
                    st.metric("Date Activated", format_date_display(card_row["Date Activated Card"]))
                with d_col3:
                    st.metric("First Charge Date", format_date_display(card_row["First Charge Date"]))


# =============================================================================
# 4. "Edit Sort Order" Page
# =============================================================================
def show_sort_order_form():
    """Displays a page to let the user manually re-order active cards."""
    st.title("Edit Manual Card Order", anchor=False)
    st.write("Change the numbers to reorder your cards. Lower numbers appear first. Click 'Save Order' when done.")
    
    all_cards_df = load_data()
    # We can only re-order active cards
    active_cards_df = all_cards_df[pd.isna(all_cards_df['Cancellation Date'])].sort_values(by="Sort Order")
    st.info("Only active cards are shown. Cancelled cards cannot be re-ordered.")
    
    with st.form("sort_order_form"):
        # If the last submission had duplicates, show an error
        if st.session_state.duplicate_sort_numbers:
                st.error(f"Found duplicate numbers: {', '.join(map(str, st.session_state.duplicate_sort_numbers))}. Please fix and save again.")
        
        # Loop through each active card and create a number input for it
        for index, card in active_cards_df.iterrows():
            col1, col2 = st.columns([1, 3])
            # Get the value from session state if it exists (for reruns on error)
            # Otherwise, use the value from the DataFrame
            default_val = st.session_state.get(f"sort_{index}", int(card["Sort Order"]))
            with col1:
                st.number_input(
                    "Order", value=default_val, key=f"sort_{index}", step=1, min_value=1
                )
            with col2:
                st.subheader(f"{card['Bank']} {card['Card Name']}", anchor=False)
                # Show an error on the specific row if it's a duplicate
                if default_val in st.session_state.duplicate_sort_numbers:
                    st.error("This number is a duplicate.")
            st.divider()

        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("Save Order", use_container_width=True, type="primary")
        with col2:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state.duplicate_sort_numbers = []
                st.session_state.show_sort_form = False
                st.rerun() # Go back to dashboard

    # --- Form Submission Logic ---
    if submitted:
        # 1. Check for Duplicates
        all_new_orders = []
        for index in active_cards_df.index:
            # Read all the new order numbers from the form (via session state)
            all_new_orders.append(st.session_state[f"sort_{index}"])
        
        # Use Counter to find items that appear more than once
        duplicates = [item for item, count in Counter(all_new_orders).items() if count > 1]
        
        if duplicates:
            # If duplicates found:
            # 1. Save them to session state
            st.session_state.duplicate_sort_numbers = duplicates
            # 2. Rerun. The form will now show errors.
            st.rerun()
        else:
            # 2. Save the New Order
            st.session_state.duplicate_sort_numbers = [] # Clear errors
            new_orders_by_id = {
                active_cards_df.loc[index, "Card ID"]: st.session_state[f"sort_{index}"]
                for index in active_cards_df.index
            }
            
            def save_order(df):
                for card_id, new_order in new_orders_by_id.items():
                    matches = df.index[df["Card ID"] == card_id].tolist()
                    if matches:
                        df.loc[matches[0], "Sort Order"] = new_order
                return df

            update_data(save_order)
            st.success("Card order saved!")
            st.session_state.show_sort_form = False # Go back to dashboard
            st.rerun()


# =============================================================================
# 5. "Card Details" Page
# =============================================================================
def show_details_page():
    """Displays a full, clean, read-only page with all details for a single card."""
    st.title("Card Details", anchor=False)
    
    all_cards_df = load_data()
    # Get the card id from session state
    card_id = st.session_state.card_to_view
    matches = all_cards_df.index[all_cards_df["Card ID"] == card_id].tolist()
    
    # Safety check
    if card_id is None or not matches:
        st.error("Could not find card to view. Returning to dashboard."); 
        st.session_state.show_details_page = False; 
        st.rerun(); 
        return
    card_index = matches[0]
        
    # Get the single card's data
    card = all_cards_df.loc[card_index]
    
    # "Back" button to return to the dashboard
    if st.button("← Back to Dashboard"):
        st.session_state.show_details_page = False
        st.session_state.card_to_view = None
        st.rerun()
    
    st.divider()
    
    strftime_code = STRFTIME_MAP[st.session_state.date_format]
    def format_date_display(date_val):
        """Formats a date for display, returning an empty string if null."""
        if pd.isna(date_val):
            return ""
        return pd.to_datetime(date_val).strftime(strftime_code)

    # --- Main Details ---
    col1, col2 = st.columns([1, 2])
    with col1:
        # Show card image
        image_path = os.path.join(IMAGE_DIR, str(card["Image Filename"]))
        if not os.path.exists(image_path): 
            image_path = os.path.join(IMAGE_DIR, DEFAULT_IMAGE)
        if os.path.exists(image_path): 
            st.image(image_path)
        else: 
            st.caption("No Image")
            
    with col2:
        # Show card info
        title_text = f"{card['Bank']} {card['Card Name']}"
        last_4 = card.get("Last 4 Digits", "")
        if last_4:
            title_text += f" ({last_4})"
        st.subheader(title_text, anchor=False)
        
        st.markdown(f"**Annual Fee:** ${card['Annual Fee']:.2f}")
        st.markdown(f"**Fee Month:** {card['Month of Annual Fee']}")
        st.markdown(f"**Card Expiry:** {card['Card Expiry (MM/YY)']}")

        tags_str = card.get("Tags", "")
        if tags_str:
            st.markdown(f"**Tags:** `{tags_str.replace(',', ', ')}`")

    # --- Notes ---
    notes = card.get("Notes", "")
    if notes and pd.notna(notes):
        st.divider()
        st.subheader("Notes", anchor=False)
        st.text(str(notes))

    # --- Welcome Offer ---
    st.divider()
    st.subheader("Welcome Offer", anchor=False)
    bonus_offer = card.get("Bonus Offer", "")
    min_spend = card.get("Min Spend", 0.0)
    current_spend = card.get("Current Spend", 0.0)
    
    if not bonus_offer and min_spend == 0.0:
        st.write("No welcome offer details logged for this card.")
    else:
        b_col1, b_col2, b_col3 = st.columns(3)
        b_col1.metric("Bonus Offer", bonus_offer if bonus_offer else "N/A")
        b_col2.metric("Min Spend", f"${min_spend:,.2f}")
        b_col3.metric("Bonus Status", card.get("Bonus Status", "N/A"))
        
        st.metric("Min Spend Deadline", format_date_display(card["Min Spend Deadline"]))
        
        if min_spend > 0:
            # Show progress bar
            progress_pct = min(1.0, current_spend / min_spend)
            st.progress(progress_pct, text=f"${current_spend:,.0f} / ${min_spend:,.0f} spent")

    # --- Annual Fee History ---
    # This section shows the fee tracking data
    st.divider()
    st.subheader("Annual Fee History", anchor=False)
    
    af_col1, af_col2 = st.columns(2)
    with af_col1:
        st.metric("Total Times Waived", card.get("FeeWaivedCount", 0))
    with af_col2:
        st.metric("Total Times Paid", card.get("FeePaidCount", 0))

    # --- Card Dates ---
    st.divider()
    st.subheader("Card Dates", anchor=False)
    d_col1, d_col2, d_col3 = st.columns(3)
    with d_col1:
        st.metric("Date Applied", format_date_display(card["Date Applied"]))
        st.metric("Date Approved", format_date_display(card["Date Approved"]))
    with d_col2:
        st.metric("Date Received", format_date_display(card["Date Received Card"]))
        st.metric("Date Activated", format_date_display(card["Date Activated Card"]))
    with d_col3:
        st.metric("First Charge Date", format_date_display(card["First Charge Date"]))

    # --- Cancellation Info ---
    # This section only appears if the card *is* cancelled
    if pd.notna(card["Cancellation Date"]):
        st.divider()
        st.subheader("Cancellation Info", anchor=False)
        c_col1, c_col2 = st.columns(2)
        c_col1.metric("Cancelled On", format_date_display(card["Cancellation Date"]))
        c_col2.metric("Re-apply After", format_date_display(card["Re-apply Date"]))


# =============================================================================
# 6. "Manage Tags" Page
# =============================================================================
def show_tag_manager_page():
    """Displays a page to add/delete tags from the master tag list (tags.json)."""
    st.title("🏷️ Manage Tags", anchor=False)
    if st.button("← Back to Dashboard"):
        st.session_state.show_tag_manager = False
        st.rerun()
    
    st.write("Here you can add or remove tags from the master list. This list will appear as options when you add or edit a card.")
    
    all_tags = load_tags()
    
    # --- "Add New Tag" Form ---
    st.divider()
    st.subheader("Add a New Tag", anchor=False)
    # 'clear_on_submit=True' makes the text box empty after adding
    with st.form("add_tag_form", clear_on_submit=True):
        new_tag = st.text_input("New Tag Name")
        submitted = st.form_submit_button("Add Tag")
        
        if submitted and new_tag:
            if new_tag in all_tags:
                st.warning(f"Tag '{new_tag}' already exists.")
            else:
                all_tags.append(new_tag)
                if save_tags(all_tags): # Save the updated list to tags.json
                    st.success(f"Added tag '{new_tag}'.")
                    st.rerun() # Rerun to update the "Existing Tags" list
                    
    st.divider()
    st.subheader("Existing Tags", anchor=False)
    
    if not all_tags:
        st.info("No tags added yet.")
        return

    # --- "Delete Tags" Form ---
    # This form shows a multiselect with all existing tags
    with st.form("delete_tags_form"):
        tags_to_delete = st.multiselect(
            "Select tags to delete",
            options=all_tags
        )
        submitted_delete = st.form_submit_button("Delete Selected Tags", type="primary")
        
        if submitted_delete and tags_to_delete:
            # Create a new list of only the tags we want to *keep*
            tags_to_keep = [tag for tag in all_tags if tag not in tags_to_delete]
            
            if save_tags(tags_to_keep):
                st.success(f"Deleted tags: {', '.join(tags_to_delete)}")
                
                # --- Cleanup: Remove deleted tags from all cards ---
                # This is an important step. If we delete a tag,
                # it should also be removed from any card that was using it.
                def remove_deleted_tags(tags_str):
                    # Convert "tag1,tag2,tag3" into a list
                    tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                    # Filter the list, keeping only tags that were *not* deleted
                    cleaned_list = [t for t in tags_list if t not in tags_to_delete]
                    # Join back into a string
                    return ",".join(cleaned_list)
                
                def clean_card_tags(df):
                    df["Tags"] = df["Tags"].apply(remove_deleted_tags)
                    return df

                update_data(clean_card_tags)
                st.rerun() # Rerun to show the updated tag list
        elif submitted_delete:
            st.warning("Please select at least one tag to delete.")


# =============================================================================
# MAIN APP "ROUTER"
# =============================================================================
def main():
    """Main function that runs the app and controls page routing."""

    # --- Custom CSS ---
    # This CSS is injected into the page head
    st.markdown("""
    <style>
    /* Style for all card images (in the list and on detail/edit pages) */
    .stImage img {
        width: 158px;    /* Fixed width */
        height: 100px;   /* Fixed height */
        object-fit: contain; /* Ensures aspect ratio is maintained */
    }
    
    /* Small layout fix to reduce space between buttons on dashboard */
    [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stContainer"] {
        margin-top: 10px;
    }
    
    /* CSS FOR TAG BUTTONS (on Manage Tags page) */
    button[title^="Click to delete tag:"] {
        background-color: #31333F;
        color: #FAFAFA;
        border: 1px solid #555555;
        border-radius: 20px;
        padding: 4px 12px;
        margin: 0;
        transition: background-color 0.2s ease, border-color 0.2s ease;
    }
    button[title^="Click to delete tag:"]:hover {
        background-color: #44444A;
        border-color: #777777;
    }
    button[title^="Click to delete tag:"]:active {
        background-color: #2A2B32;
        border-color: #555555;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Load Data ---
    # Load the data once here. It will be passed to the dashboard
    # or re-loaded by the other pages if they need to make changes.
    all_cards_df = load_data()
    card_mapping = get_card_mapping()
    
    # --- Persistent Sidebar ---
    # This sidebar code is now in main(), so it appears on *all pages*

    # --- Home Button ---
    if st.sidebar.button("🏠 Home", use_container_width=True):
        # Reset all page flags to return to the dashboard
        st.session_state.show_add_form = False
        st.session_state.show_edit_form = False
        st.session_state.show_sort_form = False
        st.session_state.show_details_page = False
        st.session_state.show_tag_manager = False
        
        # Reset any "context" flags
        st.session_state.card_to_edit = None
        st.session_state.card_to_view = None
        st.session_state.card_to_delete = None
        
        # Reset any form-specific states for a clean return
        st.session_state.duplicate_sort_numbers = []
        st.session_state.uploaded_image_preview = None
        st.session_state.image_uploader_key = str(datetime.now().timestamp())
        
        # Rerun to refresh the page to the dashboard
        st.rerun()
    
    st.sidebar.selectbox("Select Date Display Format", options=DATE_FORMATS, key="date_format")
    
    # Sidebar buttons that act as navigation
    if st.sidebar.button("Add New Card", use_container_width=True):
        st.session_state.show_add_form = True
        st.session_state.add_form_loaded = False # Reset add form preview
        st.rerun()
    if st.sidebar.button("Manage Tags", use_container_width=True):
        st.session_state.show_tag_manager = True; st.rerun()
        
    st.sidebar.divider()
    
    # This checkbox value is created here and passed to show_dashboard()
    show_cancelled = st.sidebar.checkbox("Show Cancelled Cards", value=True)
    
    # Export data button
    try:
        csv_data = all_cards_df.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button(
            label="Export Card Data (CSV)", data=csv_data,
            file_name="my_cards_backup.csv", mime="text/csv",
            use_container_width=True
        )
    except Exception as e:
        st.sidebar.error(f"Error exporting data: {e}")


    # --- Page Routing Logic ---
    # This is the "router" for the single-page app.
    # It checks the session state flags (which are True/False)
    # in order, and runs the function for the *first* flag it
    # finds that is True.
    # If all flags are False, it shows the default dashboard.
    if st.session_state.show_add_form:
        show_add_card_form(card_mapping)
        
    elif st.session_state.show_edit_form:
        show_edit_form()
        
    elif st.session_state.show_sort_form:
        show_sort_order_form()
        
    elif st.session_state.show_details_page:
        show_details_page()
        
    elif st.session_state.show_tag_manager:
        show_tag_manager_page()
        
    elif all_cards_df.empty:
        # --- "Empty State" Page ---
        # If no flags are set AND the dataframe is empty,
        # show a special "Welcome" page.
        st.title("Welcome to your Credit Card Tracker!", anchor=False)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Add Your First Card", use_container_width=True, type="primary"):
                st.session_state.show_add_form = True
                st.session_state.add_form_loaded = False # Reset add form
                st.rerun()
    else:
        # --- Default Page ---
        # If no other page flag is set, show the main dashboard.
        show_dashboard(all_cards_df, show_cancelled)

# Standard Python entry point
if __name__ == "__main__":
    main()
