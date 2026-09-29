const SESSION_KEY = "emp_session";

export const setSession = (employee) => {
  localStorage.setItem(SESSION_KEY, JSON.stringify(employee));
};

export const getSession = () => {
  try {
    const s = localStorage.getItem(SESSION_KEY);
    return s ? JSON.parse(s) : null;
  } catch {
    return null;
  }
};

export const clearSession = () => {
  localStorage.removeItem(SESSION_KEY);
};