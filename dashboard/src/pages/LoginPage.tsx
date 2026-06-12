import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Brain, Github } from "lucide-react";
import { storeToken, isAuthenticated } from "../api/client";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v2";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      storeToken(token);
      navigate("/observations", { replace: true });
    }
  }, [searchParams, navigate]);

  useEffect(() => {
    if (isAuthenticated()) {
      navigate("/observations", { replace: true });
    }
  }, [navigate]);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 mb-4">
            <Brain className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Sign in to Loom
          </h1>
          <p className="text-sm text-gray-500 mt-1.5">
            The memory layer for your AI coding agents
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-3">
          <a
            href={`${API_BASE}/auth/login/github`}
            className="flex items-center justify-center gap-3 w-full px-4 py-3
                       bg-gray-900 text-white rounded-lg text-sm font-medium
                       hover:bg-gray-800 transition-colors"
          >
            <Github className="w-5 h-5" />
            Login with GitHub
          </a>

          <a
            href={`${API_BASE}/auth/login/google`}
            className="flex items-center justify-center gap-3 w-full px-4 py-3
                       bg-white text-gray-700 border border-gray-300 rounded-lg text-sm font-medium
                       hover:bg-gray-50 transition-colors"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Login with Google
          </a>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          By signing in, you agree to the terms of service.
        </p>
      </div>
    </div>
  );
}
