import { NavLink, Outlet } from "react-router-dom";

// Small inline SVGs instead of pulling in an icon library -- keeps this
// redesign to a single new dependency (react-router-dom), not two.
const icons = {
  roadmap: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="6" r="2.4" />
      <circle cx="12" cy="18" r="2.4" />
      <path d="M6 8.4V12a4 4 0 0 0 4 4h.5M18 8.4V12a4 4 0 0 1-4 4h-.5" />
    </svg>
  ),
  practice: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="12" cy="12" r="0.8" fill="currentColor" />
    </svg>
  ),
  mockInterview: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="13" r="7.5" />
      <path d="M12 9v4l2.6 2.6M10 2.5h4M12 5.5V2.5" />
    </svg>
  ),
};

const NAV_ITEMS = [
  { to: "/", label: "Roadmap", icon: icons.roadmap, end: true },
  { to: "/practice", label: "Practice", icon: icons.practice },
  { to: "/mock-interview", label: "Mock Interview", icon: icons.mockInterview },
];

export default function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <div className="sidebar__brand-mark">{"</>"}</div>
          <div>
            <div className="sidebar__brand-text">Interview Prep</div>
            <span className="sidebar__brand-sub">LeetCode co-pilot</span>
          </div>
        </div>

        <nav className="sidebar__nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <span className="connection-pill">
            <span className="connection-pill__dot" />
            LeetCode connected
          </span>
        </div>
      </aside>

      <div className="main-area">
        <Outlet />
      </div>
    </div>
  );
}