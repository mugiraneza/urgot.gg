const API_BASE = import.meta.env.VITE_API_BASE || "/api";

async function request(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  const response = await fetch(url.toString(), {
    headers: {
      Accept: "application/json",
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      typeof body === "string"
        ? body
        : body?.detail || body?.error || `Erreur API ${response.status}`;
    throw new Error(message);
  }

  return body;
}

export function fetchFrontMatches(params) {
  return request("/front/matches/", params);
}

export function fetchFrontDashboard(params) {
  return request("/front/dashboard/", params);
}
