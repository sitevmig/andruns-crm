import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("crm_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.includes("/login")) {
      localStorage.removeItem("crm_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function apiError(e) {
  const detail = e?.response?.data?.detail;
  if (detail == null) return "Произошла ошибка. Попробуйте ещё раз.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((x) => (x && x.msg ? x.msg : JSON.stringify(x))).join(" ");
  if (detail?.msg) return detail.msg;
  return String(detail);
}
