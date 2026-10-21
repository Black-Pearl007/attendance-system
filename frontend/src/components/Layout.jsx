import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const links = [
    ['/', 'Dashboard'],
    ['/students', 'Students'],
    ['/courses', 'Courses'],
    ['/reports', 'Reports'],
    ...(user.role === 'admin' ? [['/users', 'Users']] : []),
    ['/privacy', 'Privacy'],
  ]
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark" aria-hidden>◉</span> FaceAttend</div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          <div className="who-name">{user.name}</div>
          <div className="who-role">{user.role}</div>
          <button className="btn ghost sm" onClick={() => { logout(); nav('/login') }}>Sign out</button>
        </div>
      </aside>
      <main className="content"><Outlet /></main>
    </div>
  )
}
