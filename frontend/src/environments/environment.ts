export const environment = {
  production: false,
  apiBaseUrl: "http://localhost:8000/api",
  // MapTiler is proxied via backend so the API key stays server-side.
  // See backend/app/api/map.py — set MAPTILER_API_KEY env var on the API.
  mapStyleUrl: "http://localhost:8000/api/map/style.json",
  entra: {
    clientId: "",
    authority: "",
    redirectUri: "http://localhost:4200",
  },
};
