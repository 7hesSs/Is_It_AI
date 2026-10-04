import { useEffect, useState } from "react";
import "./App.css";
import MediaTypeTabs from "./components/MediaTypeTabs";
import UploadPanel from "./components/UploadPanel";
import CompareUploadPanel from "./components/CompareUploadPanel";
import ResultsPanel from "./components/ResultsPanel";
import SimilarityResultsPanel from "./components/SimilarityResultsPanel";
import ThemeToggle from "./components/ThemeToggle";
import AuthModal from "./components/AuthModal";
import ResetPasswordModal from "./components/ResetPasswordModal";
import ProfilePage from "./components/ProfilePage";
import Footer from "./components/Footer";
import {
  checkHealth,
  analyzeText,
  analyzeImage,
  analyzePdf,
  compareDocuments,
  submitVideo,
  pollVideoJob,
  logout as logoutRequest,
} from "./api";

function getInitialTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function App() {
  const [theme, setTheme] = useState(getInitialTheme);
  const [backendOk, setBackendOk] = useState(null);
  const [view, setView] = useState("dashboard"); // "dashboard" | "profile"
  const [mediaType, setMediaType] = useState("text");
  const [isBusy, setIsBusy] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [progress, setProgress] = useState(null);
  const [errorText, setErrorText] = useState("");
  const [result, setResult] = useState(null);

  // Auth state, persisted so a refresh doesn't log the user out
  const [authToken, setAuthToken] = useState(() => localStorage.getItem("authToken"));
  const [authEmail, setAuthEmail] = useState(() => localStorage.getItem("authEmail"));
  const [authModalMode, setAuthModalMode] = useState(null); // null | "login" | "signup" | "forgot"

  // If a password-reset email link opened this page, it looks like
  // ?resetToken=xyz - pull that out once on load.
  const [resetToken, setResetToken] = useState(
    () => new URLSearchParams(window.location.search).get("resetToken")
  );

  const isLoggedIn = !!authToken;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    checkHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  // Profile is only reachable while logged in - bounce back if logged out
  // while viewing it (e.g. session expired).
  useEffect(() => {
    if (!isLoggedIn && view === "profile") setView("dashboard");
  }, [isLoggedIn, view]);

  const clearResetTokenFromUrl = () => {
    setResetToken(null);
    window.history.replaceState({}, "", window.location.pathname);
  };

  const handleAuthSuccess = (token, email) => {
    setAuthToken(token);
    setAuthEmail(email);
    localStorage.setItem("authToken", token);
    localStorage.setItem("authEmail", email);
    setAuthModalMode(null);
  };

  const handleLogout = async () => {
    if (authToken) {
      try {
        await logoutRequest(authToken);
      } catch {
        // Logging out client-side regardless is fine even if the request fails
      }
    }
    setAuthToken(null);
    setAuthEmail(null);
    localStorage.removeItem("authToken");
    localStorage.removeItem("authEmail");
    setView("dashboard");
  };

  const switchMediaType = (type) => {
    setMediaType(type);
    setResult(null);
    setErrorText("");
    setStatusText("");
    setProgress(null);
  };

  const handleClear = () => {
    setResult(null);
    setErrorText("");
    setStatusText("");
    setProgress(null);
  };

  const handleSubmit = async ({ text, file, fileA, fileB }) => {
    if (!isLoggedIn) {
      setErrorText("Log in to run this analysis.");
      return;
    }

    setIsBusy(true);
    setErrorText("");
    setResult(null);
    setProgress(null);
    setStatusText("");

    try {
      if (mediaType === "text") {
        setStatusText("Scoring text…");
        const res = await analyzeText(text, authToken);
        setResult(res);
      } else if (mediaType === "image") {
        setStatusText("Scoring image…");
        const res = await analyzeImage(file, authToken);
        setResult(res);
      } else if (mediaType === "pdf") {
        setStatusText("Extracting and scoring PDF…");
        const res = await analyzePdf(file, authToken);
        setResult(res);
      } else if (mediaType === "compare") {
        setStatusText("Comparing documents…");
        const res = await compareDocuments(fileA, fileB, authToken);
        setResult(res);
      } else {
        setStatusText("Uploading video…");
        const { job_id } = await submitVideo(file, authToken);
        setStatusText("Sampling frames…");
        const res = await pollVideoJob(job_id, authToken, {
          onProgress: (job) => {
            const p = job.progress;
            if (p?.frames_total) {
              setProgress(Math.round((p.frames_done / p.frames_total) * 100));
              setStatusText(`Analyzing frame ${p.frames_done} of ${p.frames_total}…`);
            }
          },
        });
        setResult(res);
      }
    } catch (err) {
      if (err.isAuthError) {
        setAuthToken(null);
        setAuthEmail(null);
        localStorage.removeItem("authToken");
        localStorage.removeItem("authEmail");
        setErrorText("Your session expired. Please log in again.");
      } else {
        setErrorText(err.message || "Something went wrong.");
      }
    } finally {
      setIsBusy(false);
      setStatusText("");
      setProgress(null);
    }
  };

  return (
    <div className="page">
      <div className="shell">
        <header className="masthead">
          <div className="masthead-top">
            <h1 className="brand-title" onClick={() => setView("dashboard")}>
              Is it AI?
            </h1>
            <div className="header-actions">
              <ThemeToggle
                theme={theme}
                onToggle={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
              />
              {isLoggedIn ? (
                <div className="account-chip">
                  <button className="link-button" onClick={() => setView("profile")}>
                    {authEmail}
                  </button>
                  <button className="link-button" onClick={handleLogout}>
                    Log out
                  </button>
                </div>
              ) : (
                <div className="auth-buttons">
                  <button className="auth-button ghost" onClick={() => setAuthModalMode("login")}>
                    Log in
                  </button>
                  <button className="auth-button" onClick={() => setAuthModalMode("signup")}>
                    Sign up
                  </button>
                </div>
              )}
            </div>
          </div>
          <p>
            Upload text, an image, or a video, and get a probability estimate
            of AI-generated content, broken down by the signals behind it.
          </p>
          <div className={`backend-status ${backendOk === null ? "" : backendOk ? "ok" : "down"}`}>
            <span className="dot" />
            {backendOk === null
              ? "Checking backend…"
              : backendOk
              ? "Backend connected"
              : "Backend unreachable — is the server running?"}
          </div>
        </header>

        {view === "profile" ? (
          <ProfilePage email={authEmail} token={authToken} />
        ) : (
          <>
            <MediaTypeTabs active={mediaType} onChange={switchMediaType} />

            {mediaType === "compare" ? (
              <CompareUploadPanel
                key={mediaType}
                onSubmit={handleSubmit}
                onClear={handleClear}
                hasResult={result != null}
                isBusy={isBusy}
                isLoggedIn={isLoggedIn}
                statusText={statusText}
                errorText={errorText}
              />
            ) : (
              <UploadPanel
                key={mediaType}
                mediaType={mediaType}
                onSubmit={handleSubmit}
                onClear={handleClear}
                hasResult={result != null}
                isBusy={isBusy}
                isLoggedIn={isLoggedIn}
                statusText={statusText}
                progress={progress}
                errorText={errorText}
              />
            )}

            {mediaType === "compare" ? (
              <SimilarityResultsPanel result={result} token={authToken} />
            ) : (
              <ResultsPanel result={result} token={authToken} />
            )}
          </>
        )}
      </div>

      <Footer />

      {authModalMode && (
        <AuthModal
          mode={authModalMode}
          onClose={() => setAuthModalMode(null)}
          onSuccess={handleAuthSuccess}
          onSwitchMode={setAuthModalMode}
        />
      )}

      {resetToken && (
        <ResetPasswordModal
          token={resetToken}
          onClose={clearResetTokenFromUrl}
          onDone={() => {
            clearResetTokenFromUrl();
            setAuthModalMode("login");
          }}
        />
      )}
    </div>
  );
}

export default App;
