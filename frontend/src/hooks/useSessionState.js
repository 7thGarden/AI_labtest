import { useEffect, useState } from "react";

export default function useSessionState(key, initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = window.sessionStorage.getItem(key);
      return stored ? JSON.parse(stored) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      window.sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Ignore storage errors (private mode, quota, etc.).
    }
  }, [key, value]);

  return [value, setValue];
}
