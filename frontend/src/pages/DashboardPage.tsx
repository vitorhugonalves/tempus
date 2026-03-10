import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChartBarIcon,
  ClockIcon,
  TrophyIcon,
  UsersIcon,
} from "@heroicons/react/24/outline";
import { competitionsApi } from "../api/competitions";
import { useAuthStore } from "../store/auth";
import { Card } from "../components/ui/Card";
import type { Competition, UserRole } from "../types";

interface StatCard {
  label: string;
  value: string | number;
  Icon: React.ElementType;
  color: string;
  href?: string;
}

const ROLE_GREETINGS: Record<UserRole, string> = {
  admin: "Painel Administrativo",
  operator: "Painel do Operador",
  judge: "Painel do Juiz",
  competitor: "Painel do Competidor",
};

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [competitions, setCompetitions] = useState<Competition[]>([]);

  useEffect(() => {
    competitionsApi.list().then(({ data }) => setCompetitions(data));
  }, []);

  const active = competitions.filter((c) => c.status === "active");
  const draft = competitions.filter((c) => c.status === "draft");

  const stats: StatCard[] = [
    {
      label: "Total de Competições",
      value: competitions.length,
      Icon: TrophyIcon,
      color: "text-blue-600 bg-blue-50",
      href: "/competitions",
    },
    {
      label: "Competições Ativas",
      value: active.length,
      Icon: ClockIcon,
      color: "text-green-600 bg-green-50",
    },
    {
      label: "Em Rascunho",
      value: draft.length,
      Icon: ChartBarIcon,
      color: "text-yellow-600 bg-yellow-50",
    },
    {
      label: "Atletas Suportados",
      value: "300",
      Icon: UsersIcon,
      color: "text-purple-600 bg-purple-50",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {user ? ROLE_GREETINGS[user.role] : "Dashboard"}
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Bem-vindo, <span className="font-medium text-gray-700">{user?.full_name}</span>
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(({ label, value, Icon, color, href }) => {
          const content = (
            <Card key={label} className="flex items-center gap-4 hover:shadow-md transition-shadow">
              <div className={["rounded-xl p-3", color].join(" ")}>
                <Icon className="h-6 w-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{value}</p>
                <p className="text-sm text-gray-500">{label}</p>
              </div>
            </Card>
          );
          return href ? (
            <Link key={label} to={href} className="block">
              {content}
            </Link>
          ) : (
            <div key={label}>{content}</div>
          );
        })}
      </div>

      {/* Recent competitions */}
      <Card padding="none">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">Competições Recentes</h2>
          {(user?.role === "admin" || user?.role === "operator") && (
            <Link
              to="/competitions"
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              Ver todas
            </Link>
          )}
        </div>
        {competitions.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-400 text-sm">
            Nenhuma competição cadastrada ainda.
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {competitions.slice(0, 5).map((comp) => (
              <li key={comp.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{comp.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {comp.modality ?? "—"} · Máx. {comp.max_athletes} atletas
                  </p>
                </div>
                <StatusBadge status={comp.status} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    draft: { label: "Rascunho", className: "bg-gray-100 text-gray-600" },
    active: { label: "Ativa", className: "bg-green-100 text-green-700" },
    finished: { label: "Encerrada", className: "bg-red-100 text-red-700" },
  };
  const { label, className } = map[status] ?? map.draft;
  return (
    <span className={["text-xs font-medium rounded-full px-2.5 py-0.5", className].join(" ")}>
      {label}
    </span>
  );
}
