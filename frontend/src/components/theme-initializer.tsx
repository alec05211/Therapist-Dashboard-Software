"use client";

import { useEffect } from "react";

export function ThemeInitializer() {
  useEffect(() => {
    const theme = window.localStorage.getItem("therapist-dashboard-theme") === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, []);

  return null;
}
