import { redirect } from "next/navigation";

/*
 * The app has no public landing page. Signed-in staff land on the
 * dashboard; the dashboard sends anyone without a valid session to /login.
 */
export default function Home() {
  redirect("/dashboard");
}
