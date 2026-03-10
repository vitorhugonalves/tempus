import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4 text-center">
      <p className="text-8xl font-bold text-gray-200 select-none">404</p>
      <h1 className="text-2xl font-bold text-gray-900 mt-4">Página não encontrada</h1>
      <p className="text-gray-500 text-sm mt-2 max-w-sm">
        A página que você tentou acessar não existe ou foi removida.
      </p>
      <Link
        to="/dashboard"
        className="mt-8 inline-flex items-center rounded-lg bg-primary-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
      >
        Voltar ao Dashboard
      </Link>
    </div>
  );
}
