import { Outlet } from "react-router-dom";

export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-900 via-primary-700 to-primary-500 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white tracking-tight">Tempus</h1>
          <p className="text-primary-200 mt-2 text-sm">
            Gerenciador de Timers para Competições
          </p>
        </div>
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <Outlet />
        </div>
        <p className="text-center text-primary-200 text-xs mt-6">
          &copy; {new Date().getFullYear()} Tempus. Todos os direitos reservados.
        </p>
      </div>
    </div>
  );
}
