const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep default message.
    }
    throw new Error(message);
  }

  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response;
}

export const api = {
  cards: () => request("/api/cards"),
  createCard: (card) => request("/api/cards", { method: "POST", body: JSON.stringify(card) }),
  updateCard: (id, card) => request(`/api/cards/${id}`, { method: "PUT", body: JSON.stringify(card) }),
  deleteCard: (id) => request(`/api/cards/${id}`, { method: "DELETE" }),
  cancelCard: (id) => request(`/api/cards/${id}/cancel`, { method: "POST" }),
  reactivateCard: (id) => request(`/api/cards/${id}/reactivate`, { method: "POST" }),
  addSpend: (id, amount) => request(`/api/cards/${id}/spend`, { method: "POST", body: JSON.stringify({ amount }) }),
  feeAction: (id, action) => request(`/api/cards/${id}/fee-action`, { method: "POST", body: JSON.stringify({ action }) }),
  sortOrder: (orders) => request("/api/sort-order", { method: "POST", body: JSON.stringify({ orders }) }),
  tags: () => request("/api/tags"),
  saveTags: (tags) => request("/api/tags", { method: "POST", body: JSON.stringify({ tags }) }),
  deleteTag: (tag) => request(`/api/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),
  uploadImage: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/images", { method: "POST", body: form });
  },
  backup: () => request("/api/backups", { method: "POST" }),
};

export function imageUrl(filename) {
  return `${API_BASE}/card_images/${encodeURIComponent(filename || "default.png")}`;
}
