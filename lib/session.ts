import { v4 as uuidv4 } from "uuid";

export function getSessionId(): string {
  if (typeof window === "undefined") return "server";
  let id = localStorage.getItem("parity_session_id");
  if (!id) {
    id = uuidv4();
    localStorage.setItem("parity_session_id", id);
  }
  return id;
}
