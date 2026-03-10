import { ClockIcon } from "@heroicons/react/24/outline";
import { Card } from "../components/ui/Card";

export default function TimersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Timers</h1>
        <p className="text-gray-500 text-sm mt-1">
          Controle os timers dos atletas em tempo real
        </p>
      </div>

      <Card className="flex flex-col items-center justify-center py-16 text-center">
        <ClockIcon className="h-12 w-12 text-gray-200 mb-4" />
        <p className="text-gray-500 font-medium">Em desenvolvimento</p>
        <p className="text-gray-400 text-sm mt-1">
          O controle de timers em tempo real estará disponível em breve.
        </p>
      </Card>
    </div>
  );
}
