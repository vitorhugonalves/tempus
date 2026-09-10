import { useState } from "react";
import { useParams } from "react-router-dom";
import { checkinApi } from "../../api/checkin";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Alert from "../../components/ui/Alert";
import type { Athlete, CheckinCandidate } from "../../types";

export default function CheckinPage() {
  const { competitionId } = useParams<{ competitionId: string }>();
  const id = Number(competitionId);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CheckinCandidate[]>([]);
  const [checkedIn, setCheckedIn] = useState<Athlete | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setError(null);
    setCheckedIn(null);
    setSearching(true);
    try {
      const data = await checkinApi.search(id, query.trim());
      setResults(data);
    } catch {
      setError("Erro ao buscar");
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function handleEnsure(candidate: CheckinCandidate) {
    setError(null);
    try {
      const athlete = await checkinApi.ensure(id, candidate.kind, candidate.source_id);
      setCheckedIn(athlete);
      setResults([]);
      setQuery("");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erro ao confirmar check-in");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Check-in</h1>

      {error && <Alert variant="error">{error}</Alert>}
      {checkedIn && (
        <Alert variant="success">
          Check-in confirmado: <strong>{checkedIn.name}</strong> — equipe{" "}
          {checkedIn.team_name}. Prossiga para o pareamento de tag.
        </Alert>
      )}

      <form onSubmit={handleSearch} className="flex gap-2">
        <Input
          placeholder="Buscar por nome ou e-mail..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" disabled={searching}>Buscar</Button>
      </form>

      <div className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
        {results.length === 0 ? (
          <p className="p-6 text-center text-sm text-gray-500">
            {searching ? "Buscando..." : "Nenhum resultado ainda."}
          </p>
        ) : (
          results.map((c) => (
            <div key={`${c.kind}-${c.source_id}`} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium text-gray-900">{c.name}</p>
                <p className="text-xs text-gray-500">
                  {c.email ?? "—"} ·{" "}
                  {c.kind === "athlete"
                    ? `Equipe ${c.team_name ?? "—"}`
                    : "Inscrito online — sem check-in ainda"}
                </p>
              </div>
              <Button onClick={() => handleEnsure(c)} className="text-sm">
                {c.has_athlete_record ? "Selecionar" : "Confirmar check-in"}
              </Button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
