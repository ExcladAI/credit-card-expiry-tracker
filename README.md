# Credit Card Tracker

A self-hosted, local-first application designed to track credit card usage, annual fee deadlines, and sign-up bonuses. The default web UI is now a React dashboard served by FastAPI, with the Telegram bot running beside it for mobile interactions and notifications.

## Project Structure

The application runs as two concurrent processes sharing a single CSV database (`my_cards.csv`).

### 1\. React + FastAPI Web Dashboard

Built with **React** in `frontend/` and **FastAPI** in `api.py`.

  * **Purpose:** Full management of the card portfolio.
  * **Capabilities:**
      * Add, edit, and delete card entries.
      * Upload and manage card images.
      * Visual dashboard for annual fee liabilities and upcoming dates.
      * Manage custom tags.
      * "Met" status tracking for sign-up bonuses.

### 2\. `bot.py` (Telegram Service)

Built with **python-telegram-bot**, this file runs as a background service.

  * **Purpose:** Mobile access and automated alerting.
  * **Capabilities:**
      * **Read-only access:** Quickly view card details and fee dates via commands.
      * **Spend Tracking:** Update "Current Spend" for active bonuses directly from chat.
      * **Notifications:** Runs a weekly scheduler to alert you of unpaid annual fees or expiring bonus deadlines.
      * **Backup:** automated daily backups of the CSV database.

-----

## Configuration

Both the local and Docker deployments require environment variables. Create a `.env` file in the root directory:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_USER_ID=your_telegram_user_id
DATA_FILE=my_cards.csv
```

-----

## Running Locally

### Prerequisites

  * Python 3.13+
  * pip

### Installation

1.  Clone the repository and navigate to the folder.
2.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Install frontend dependencies:
    ```bash
    cd frontend
    npm install
    npm run build
    cd ..
    ```
4.  Ensure your `.env` file is configured.

### Execution

Since the application requires both the web UI and the bot to run simultaneously, you must execute them in parallel.

**Option 1: Two Terminals**
Open two separate terminal windows.

Terminal 1 (Web UI/API):

```bash
uvicorn api:app --host 0.0.0.0 --port=8502
```

Terminal 2 (Bot):

```bash
python3 bot.py
```

**Option 2: Shell Script (Linux/Mac)**
Run the included helper script:

```bash
chmod +x run.sh
./run.sh
```

The previous Streamlit UI remains available as a fallback:

```bash
streamlit run main.py --server.port=8503
```

-----

## Running on NAS (Docker/Portainer)

This application is designed to be deployed via Docker Compose (or Portainer Stacks).

### 1\. Prepare Directory

On your NAS, create a directory (e.g., `/docker/credit-card-tracker`) and upload the following files:

  * `my_cards.csv` (can be an empty file initially)
  * `my_tags.json`
  * `.env`
  * Folder: `card_images/`
  * Folder: `backups/`

### 2\. Docker Compose Configuration

Build the image first:

```bash
docker build -t credit-card-tracker:latest .
```

Then use the following configuration in your Portainer Stack or `docker-compose.yml`.

**Note:** This configuration overrides the default container command to ensure both processes run reliably without requiring internal shell scripts.

```yaml
services:
  app:
    image: credit-card-tracker:latest
    container_name: card_tracker_app
    restart: unless-stopped
    
    # Network: Ensure this matches your existing Docker network
    networks:
      - allowed-internet

    ports:
      - "5822:8502" # Host Port : Container Port

    # supervisor.py starts both the bot and FastAPI/React, and stops the container
    # if either process exits.
    command: python3 supervisor.py
    
    # Resource Limits (Optional but recommended for NAS)
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          memory: 128M

    # Volume Mapping: Persist data to your NAS
    volumes:
      - /path/to/nas/my_cards.csv:/app/my_cards.csv
      - /path/to/nas/my_tags.json:/app/my_tags.json
      - /path/to/nas/card_images:/app/card_images
      - /path/to/nas/backups:/app/backups
      - /path/to/nas/.env:/app/.env

networks:
  allowed-internet:
    external: true
```

### 3\. Access

Once deployed, the web dashboard will be available at:
`http://<YOUR_NAS_IP>:5822`

The Telegram bot will respond immediately to the `/start` command.
