import HistoryPanel from "./HistoryPanel";

export default function ProfilePage({ email, token }) {
  return (
    <div className="profile-page">
      <h2 className="profile-heading">Profile</h2>
      <p className="profile-email">{email}</p>
      <HistoryPanel token={token} />
    </div>
  );
}
