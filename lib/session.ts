import { v4 as uuidv4 } from "uuid";

export function getOrCreateParityUserId(): string {
  if (typeof window === "undefined") return "";
  let id: string | null = localStorage.getItem("parity_user_id");
  if (!id) {
    id = uuidv4();
    localStorage.setItem("parity_user_id", id);
  }
  return id;
}

export function getSessionId(): string {
  return getOrCreateParityUserId();
}
