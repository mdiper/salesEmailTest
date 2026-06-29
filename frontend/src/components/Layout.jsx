import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h2>SalesEmail</h2>
          <span className="user-badge">{user?.username}</span>
        </div>
        <ul className="nav-links">
          <li>
            <NavLink to="/" end>
              Dashboard
            </NavLink>
          </li>
          <li>
            <NavLink to="/emails">Email</NavLink>
          </li>
          <li>
            <NavLink to="/rules">Regole</NavLink>
          </li>
          <li>
            <NavLink to="/forwarding">Reindirizzamenti</NavLink>
          </li>
        </ul>
        <button className="logout-btn" onClick={logout}>
          Logout
        </button>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
