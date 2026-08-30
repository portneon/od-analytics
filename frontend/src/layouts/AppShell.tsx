import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/datasets', label: 'Datasets' },
]

export function AppShell() {
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col border-r border-slate-200 bg-white">
        <div className="px-4 py-5">
          <p className="text-sm font-semibold text-slate-900">Email Intelligence</p>
          <p className="text-xs text-slate-400">Executive Analytics Platform</p>
        </div>
        <nav className="flex-1 space-y-0.5 px-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-x-hidden bg-slate-50">
        <Outlet />
      </main>
    </div>
  )
}
