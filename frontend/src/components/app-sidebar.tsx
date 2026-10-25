import { Activity, LayoutDashboard, LineChart, Wind } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

const NAV_ITEMS = [
  { to: '/', title: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/predictions', title: 'Prediction Data', icon: LineChart, end: false },
  { to: '/actuals', title: 'Actual Data', icon: Activity, end: false },
] as const

export function AppSidebar() {
  const { pathname } = useLocation()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-1 py-1.5 group-data-[collapsible=icon]:justify-center">
          <span className="flex size-7 shrink-0 items-center justify rounded-md bg-primary text-primary-foreground">
            <Wind className="size-4" />
          </span>
          <span className="grid flex-1 text-left leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate font-semibold">WindSight</span>
            <span className="truncate text-xs text-muted-foreground">
              Day-ahead wind intelligence
            </span>
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Analysis</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map(({ to, title, icon: Icon, end }) => {
                const active = end ? pathname === to : pathname.startsWith(to)
                return (
                  <SidebarMenuItem key={to}>
                    <SidebarMenuButton asChild isActive={active} tooltip={title}>
                      <NavLink to={to} end={end}>
                        <Icon />
                        <span>{title}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <p className="px-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
          Elexon BMRS · January 2026
        </p>
      </SidebarFooter>
    </Sidebar>
  )
}
