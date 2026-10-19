export function saveToken(token: string) {
  sessionStorage.setItem("access_token", token);
}

export function getToken() {
  return sessionStorage.getItem("access_token");
}

export function removeToken() {
  sessionStorage.removeItem("access_token");
}

export function isAuthenticated() {
  return !!getToken();
}
