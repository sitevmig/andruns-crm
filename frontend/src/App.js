import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Organizations from "@/pages/Organizations";
import Import from "@/pages/Import";
import Queue from "@/pages/Queue";
import Templates from "@/pages/Templates";
import ExportPage from "@/pages/Export";
import Journal from "@/pages/Journal";
import Settings from "@/pages/Settings";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null)
    return <div className="flex h-screen items-center justify-center text-muted-foreground">Загрузка…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <Protected>
                  <Layout />
                </Protected>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="organizations" element={<Organizations />} />
              <Route path="import" element={<Import />} />
              <Route path="queue" element={<Queue />} />
              <Route path="templates" element={<Templates />} />
              <Route path="export" element={<ExportPage />} />
              <Route path="journal" element={<Journal />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
