import { useState } from "react";
import { signup, login, forgotPassword } from "../api";

export default function AuthModal({ mode, onClose, onSuccess, onSwitchMode }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  const isSignup = mode === "signup";
  const isForgot = mode === "forgot";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setInfoMessage("");
    setIsBusy(true);

    try {
      if (isForgot) {
        const result = await forgotPassword(email.trim());
        setInfoMessage(result.message);
      } else {
        const action = isSignup ? signup : login;
        const result = await action(email.trim(), password);
        onSuccess(result.token, result.email);
      }
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const title = isForgot ? "Reset your password" : isSignup ? "Create an account" : "Log in";

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {infoMessage ? (
          <>
            <p className="modal-info">{infoMessage}</p>
            <button
              type="button"
              className="analyze-button modal-submit"
              onClick={() => onSwitchMode("login")}
            >
              Back to log in
            </button>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <label className="field-label" htmlFor="auth-email">
              Email
            </label>
            <input
              id="auth-email"
              type="email"
              className="text-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />

            {!isForgot && (
              <>
                <label className="field-label" htmlFor="auth-password">
                  Password
                </label>
                <input
                  id="auth-password"
                  type="password"
                  className="text-field"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  autoComplete={isSignup ? "new-password" : "current-password"}
                  required
                />
                {isSignup && <div className="field-hint">At least 8 characters.</div>}
              </>
            )}

            {!isSignup && !isForgot && (
              <button
                type="button"
                className="link-button forgot-link"
                onClick={() => onSwitchMode("forgot")}
              >
                Forgot password?
              </button>
            )}

            {error && <p className="error-text">{error}</p>}

            <button className="analyze-button modal-submit" disabled={isBusy} type="submit">
              {isBusy ? "Please wait…" : isForgot ? "Send reset link" : isSignup ? "Sign up" : "Log in"}
            </button>
          </form>
        )}

        {!infoMessage && (
          <p className="modal-switch">
            {isForgot ? (
              <button type="button" className="link-button" onClick={() => onSwitchMode("login")}>
                Back to log in
              </button>
            ) : (
              <>
                {isSignup ? "Already have an account? " : "Don't have an account? "}
                <button
                  type="button"
                  className="link-button"
                  onClick={() => onSwitchMode(isSignup ? "login" : "signup")}
                >
                  {isSignup ? "Log in" : "Sign up"}
                </button>
              </>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
