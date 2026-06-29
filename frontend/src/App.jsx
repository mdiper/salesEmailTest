import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import EmailList from "./pages/EmailList";
import EmailDetail from "./pages/EmailDetail";
import Rules from "./pages/Rules";
import Forwarding from "./pages/Forwarding";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/emails" element={<EmailList />} />
            <Route path="/emails/:id" element={<EmailDetail />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/forwarding" element={<Forwarding />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
