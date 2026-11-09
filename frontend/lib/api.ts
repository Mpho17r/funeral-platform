import axios from "axios";

import { removeToken } from "@/lib/auth";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});


api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const hadAuthenticatedRequest = Boolean(
      error?.config?.headers?.Authorization,
    );

    if (
      typeof window !== "undefined" &&
      status === 401 &&
      hadAuthenticatedRequest
    ) {
      // A rejected authenticated request means the session is no longer
      // valid. Clear it centrally so every protected route behaves alike.
      removeToken();
      window.dispatchEvent(new Event("linda-session-expired"));
    }

    return Promise.reject(error);
  },
);

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = sessionStorage.getItem("access_token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }

  // Let the browser/Axios set the correct multipart/form-data
  // Content-Type and boundary when sending FormData.
  if (
    typeof FormData !== "undefined" &&
    config.data instanceof FormData
  ) {
    delete config.headers["Content-Type"];
  }

  return config;
});

export default api;
