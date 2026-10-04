const BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function handleResponse(res) {
  if (res.status === 401) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || "Please log in to continue.");
    err.isAuthError = true;
    throw err;
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function checkHealth() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function signup(email, password) {
  const res = await fetch(`${BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res);
}

export async function login(email, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res);
}

export async function forgotPassword(email) {
  const res = await fetch(`${BASE}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  return handleResponse(res);
}

export async function resetPassword(token, newPassword) {
  const res = await fetch(`${BASE}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  return handleResponse(res);
}

export async function logout(token) {
  await fetch(`${BASE}/auth/logout`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function analyzeText(text, token) {
  const res = await fetch(`${BASE}/analyze/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ text }),
  });
  return handleResponse(res);
}

export async function analyzeImage(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/analyze/image`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handleResponse(res);
}

export async function analyzePdf(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/analyze/pdf`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handleResponse(res);
}

export async function compareDocuments(fileA, fileB, token) {
  const formData = new FormData();
  formData.append("file_a", fileA);
  formData.append("file_b", fileB);
  const res = await fetch(`${BASE}/analyze/similarity`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handleResponse(res);
}

export async function submitVideo(file, token) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/analyze/video`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handleResponse(res);
}

export async function getVideoJobStatus(jobId, token) {
  const res = await fetch(`${BASE}/analyze/video/${jobId}`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

export async function downloadReport(scanId, token) {
  const res = await fetch(`${BASE}/scans/${scanId}/report`, {
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `is-it-ai-report-${scanId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function getScanHistory(token, limit = 10) {
  const res = await fetch(`${BASE}/scans?limit=${limit}`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

export async function getScan(token, scanId) {
  const res = await fetch(`${BASE}/scans/${scanId}`, {
    headers: authHeaders(token),
  });
  return handleResponse(res);
}

/**
 * Polls a video job until it's done or errored, calling onProgress after
 * each check. Returns the final result payload.
 */
export async function pollVideoJob(jobId, token, { onProgress, intervalMs = 1500 } = {}) {
  while (true) {
    const job = await getVideoJobStatus(jobId, token);
    if (onProgress) onProgress(job);

    if (job.status === "done") return job.result;
    if (job.status === "error") throw new Error(job.error || "Video analysis failed");

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
