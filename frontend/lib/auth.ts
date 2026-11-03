export function saveToken(token: string) {
  sessionStorage.setItem("access_token", token);

  // Let the parts of the app that wait for a sign-in (business name, logo,
  // colours) load now rather than on the next page refresh.
  window.dispatchEvent(new Event("linda-signed-in"));
}

export function getToken() {
  return sessionStorage.getItem("access_token");
}

export function removeToken() {
  sessionStorage.removeItem("access_token");
  window.dispatchEvent(new Event("linda-signed-in"));
}

export function isAuthenticated() {
  return !!getToken();
}
