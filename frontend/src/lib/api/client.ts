const DEFAULT_API_BASE_URL = "http://localhost:8000";
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL = (configuredApiBaseUrl || DEFAULT_API_BASE_URL).replace(/\/$/, "");

if (!configuredApiBaseUrl) {
  console.info(`VITE_API_BASE_URL is not set; using ${DEFAULT_API_BASE_URL}`);
}

function urlFor(path: string) {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function logApiFailure(path: string, message: string) {
  if (import.meta.env.DEV) {
    console.warn("API request failed", { path, baseUrl: API_BASE_URL, message });
  }
}

async function parseApiError(response: Response) {
  let message = `API request failed with ${response.status}`;
  try {
    const payload = await response.json();
    message = payload.detail || payload.error || message;
  } catch {
    // Keep the HTTP status message.
  }
  return message;
}

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(urlFor(path));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network request failed";
    logApiFailure(path, message);
    throw error;
  }
  if (!response.ok) {
    const message = await parseApiError(response);
    logApiFailure(path, message);
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(urlFor(path), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network request failed";
    logApiFailure(path, message);
    throw error;
  }
  if (!response.ok) {
    const message = await parseApiError(response);
    logApiFailure(path, message);
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(urlFor(path), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network request failed";
    logApiFailure(path, message);
    throw error;
  }
  if (!response.ok) {
    const message = await parseApiError(response);
    logApiFailure(path, message);
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
