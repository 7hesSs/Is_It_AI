import { useState } from "react";
import { resetPassword } from "../api";

export default function ResetPasswordModal({ token, onClose, onDone }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setIsBusy(true);
    try {
      await resetPassword(token, password);
      setIsDone(true);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <h2>{isDone ? "Password updated" : "Set a new password"}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {isDone ? (
          <>
            <p className="modal-info">
              Your password has been updated. You can log in with it now.
            </p>
            <button className="analyze-button modal-submit" onClick={onDone}>
              Log in
            </button>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <label className="field-label" htmlFor="new-password">
              New password
            </label>
            <input
              id="new-password"
              type="password"
              className="text-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              autoComplete="new-password"
              required
            />
            <div className="field-hint">At least 8 characters.</div>

            {error && <p className="error-text">{error}</p>}

            <button className="analyze-button modal-submit" disabled={isBusy} type="submit">
              {isBusy ? "Please wait…" : "Update password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
