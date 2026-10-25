import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppHeader } from '@/components/app-header'
import { AppSidebar } from '@/components/app-sidebar'
import { ThemeProvider } from '@/components/theme-provider'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { HealthProvider } from '@/health-context'
import { ActualDataPage } from '@/pages/actual-data'
import { DashboardPage } from '@/pages/dashboard'
import { PredictionDataPage } from '@/pages/prediction-data'

export default function App() {
  return (
    <ThemeProvider>
      <HealthProvider>
        <TooltipProvider delayDuration={0}>
          <BrowserRouter>
            <SidebarProvider>
              <AppSidebar />
              <SidebarInset>
                <AppHeader />
                <div className="mx-auto w-full max-w-[1400px] space-y-4 p-4 md:p-6">
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/predictions" element={<PredictionDataPage />} />
                    <Route path="/actuals" element={<ActualDataPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </div>
              </SidebarInset>
            </SidebarProvider>
          </BrowserRouter>
        </TooltipProvider>
      </HealthProvider>
    </ThemeProvider>
  )
}
