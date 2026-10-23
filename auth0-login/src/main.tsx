import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { LoginScreen } from "./login-screen";
import "./styles.css";

declare global {
  interface Window {
    universal_login_context?: unknown;
  }
}

const root = document.getElementById("root") ?? document.body.appendChild(
  Object.assign(document.createElement("div"), { id: "root" }),
);

createRoot(root).render(
  <StrictMode>
    <LoginScreen preview={!window.universal_login_context} />
  </StrictMode>,
);
