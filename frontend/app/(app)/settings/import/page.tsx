import { redirect } from "next/navigation";

// Importing moved out of Settings; keep old bookmarks and links working.
export default function OldImportAddress() {
  redirect("/import");
}
