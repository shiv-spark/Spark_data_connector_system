import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export const api = axios.create({
  baseURL,
  timeout: 120_000, // 2 min — analyze/ingest can take 20–60s due to LLM + heavy queries
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.code === "ECONNABORTED") {
      err.message = "Request timed out. Is the backend running?";
    } else if (!err.response) {
      err.message = "Cannot reach the API. Is the container up?";
    }
    return Promise.reject(err);
  },
);

export const fetchHealth = async () => {
  const r = await api.get("/health");
  return r.data;
};