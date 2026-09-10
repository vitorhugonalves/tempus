import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import {
  competitionsApi,
  type CompetitorRegisterRequest,
  type MemberInput,
} from "../api/competitions";
import { categoriesApi } from "../api/categories";
import { authApi } from "../api/auth";
import { consentTermApi, type ConsentTermMeta } from "../api/consentTerm";
import { useAuthStore } from "../store/auth";
import type { Category, Competition } from "../types";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";

export default function RegistrationPage() {
  const { competitionId } = useParams<{ competitionId?: string }>();
  const navigate = useNavigate();
  const { user, initialize } = useAuthStore();

  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [selectedCompetitionId, setSelectedCompetitionId] = useState<number | null>(
    competitionId ? parseInt(competitionId) : null
  );
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [document, setDocument] = useState("");
  const [boxName, setBoxName] = useState("");
  const [teamName, setTeamName] = useState("");
  const [additionalMembers, setAdditionalMembers] = useState<MemberInput[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<React.ReactNode>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [alreadyRegistered, setAlreadyRegistered] = useState(false);

  // Dados de cadastro para visitante anônimo (sem conta ainda)
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Termo de consentimento da competição selecionada
  const [consentTerm, setConsentTerm] = useState<ConsentTermMeta | null>(null);
  const [consentAccepted, setConsentAccepted] = useState(false);

  // Carrega competições ativas
  useEffect(() => {
    competitionsApi.list().then(({ data }) => {
      const active = data.filter((c) => c.status === "active");
      setCompetitions(active);
      if (!competitionId && active.length === 1) {
        setSelectedCompetitionId(active[0].id);
      }
    });
  }, [competitionId]);

  // Verifica se já está inscrito quando competição é selecionada
  useEffect(() => {
    if (!selectedCompetitionId) {
      setAlreadyRegistered(false);
      return;
    }
    competitionsApi
      .getMyRegistration(selectedCompetitionId)
      .then(({ data }) => setAlreadyRegistered(data.is_registered))
      .catch(() => setAlreadyRegistered(false));
  }, [selectedCompetitionId]);

  // Carrega categorias quando competição é selecionada
  useEffect(() => {
    if (!selectedCompetitionId) {
      setCategories([]);
      setSelectedCategoryId(null);
      return;
    }
    categoriesApi.list(selectedCompetitionId, true).then((cats) => {
      setCategories(cats);
      setSelectedCategoryId(null);
    });
  }, [selectedCompetitionId]);

  // Carrega termo de consentimento quando competição é selecionada; nunca reaproveita
  // o aceite entre competições diferentes
  useEffect(() => {
    setConsentAccepted(false);
    if (!selectedCompetitionId) {
      setConsentTerm(null);
      return;
    }
    consentTermApi
      .get(selectedCompetitionId)
      .then(setConsentTerm)
      .catch(() => setConsentTerm(null));
  }, [selectedCompetitionId]);

  const selectedCategory = categories.find((c) => c.id === selectedCategoryId) ?? null;
  const isTeam = selectedCategory?.category_type === "team";
  const maxAdditional = selectedCategory?.max_team_size
    ? selectedCategory.max_team_size - 1
    : 99;

  function addMember() {
    if (additionalMembers.length >= maxAdditional) return;
    setAdditionalMembers((prev) => [...prev, { full_name: "", email: "" }]);
  }

  function removeMember(index: number) {
    setAdditionalMembers((prev) => prev.filter((_, i) => i !== index));
  }

  function updateMember(index: number, field: keyof MemberInput, value: string) {
    setAdditionalMembers((prev) =>
      prev.map((m, i) => (i === index ? { ...m, [field]: value } : m))
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedCompetitionId || !selectedCategoryId) return;

    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      if (!user) {
        try {
          await authApi.signup({ full_name: fullName, email, password });
        } catch (err: unknown) {
          const status = (err as { response?: { status?: number } })?.response?.status;
          if (status === 409) {
            setError(
              <>
                Esse e-mail já tem conta. Faça login para continuar.{" "}
                <Link to="/login" className="underline font-medium">
                  Fazer login
                </Link>
              </>
            );
            return;
          }
          throw err;
        }
        await initialize();
      }

      const payload: CompetitorRegisterRequest = {
        category_id: selectedCategoryId,
        document: document || undefined,
        box_name: boxName || undefined,
        team_name: isTeam ? teamName : undefined,
        additional_members: isTeam ? additionalMembers : [],
        consent_accepted: consentAccepted,
      };
      const { data } = await competitionsApi.register(selectedCompetitionId, payload);
      let msg = `Inscrição realizada com sucesso! Equipe: ${data.team_name}`;
      if (data.accounts_created > 0) {
        msg += `. ${data.accounts_created} conta(s) criada(s) automaticamente — os novos membros receberão e-mail de acesso.`;
      }
      setSuccess(msg);
      // Redireciona para o ranking após 3 segundos
      setTimeout(() => navigate(`/competitions/${selectedCompetitionId}/ranking`), 3000);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Erro ao realizar inscrição. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Inscrição em Competição</h1>
        <p className="text-gray-500 text-sm mt-1">
          Inscreva-se em uma competição ativa e escolha sua categoria.
        </p>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {alreadyRegistered && !success && (
        <Alert variant="success" title="Você já está inscrito!">
          Você já realizou sua inscrição nesta competição.{" "}
          <button
            className="text-green-700 underline font-medium"
            onClick={() => navigate(`/competitions/${selectedCompetitionId}/ranking`)}
          >
            Ver ranking
          </button>
        </Alert>
      )}

      {!success && !alreadyRegistered && (
        <Card>
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Cadastro de conta — apenas para visitantes ainda não logados */}
            {!user && (
              <>
                <Input
                  label="Nome completo"
                  type="text"
                  placeholder="Seu nome"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  autoFocus
                />

                <Input
                  label="E-mail"
                  type="email"
                  placeholder="seu@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />

                <Input
                  label="Senha"
                  type="password"
                  placeholder="Mínimo 8 caracteres"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </>
            )}

            {/* Seleção de competição */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Competição
              </label>
              {competitions.length === 0 ? (
                <p className="text-sm text-gray-400">Nenhuma competição ativa disponível.</p>
              ) : (
                <select
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={selectedCompetitionId ?? ""}
                  onChange={(e) =>
                    setSelectedCompetitionId(e.target.value ? parseInt(e.target.value) : null)
                  }
                  required
                >
                  <option value="">Selecione uma competição</option>
                  {competitions.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Seleção de categoria */}
            {selectedCompetitionId && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Categoria
                </label>
                {categories.length === 0 ? (
                  <p className="text-sm text-gray-400">Nenhuma categoria disponível.</p>
                ) : (
                  <select
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    value={selectedCategoryId ?? ""}
                    onChange={(e) =>
                      setSelectedCategoryId(e.target.value ? parseInt(e.target.value) : null)
                    }
                    required
                  >
                    <option value="">Selecione uma categoria</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                        {c.category_type === "team" && c.max_team_size
                          ? ` (equipe até ${c.max_team_size} pessoas)`
                          : c.category_type === "team"
                          ? " (equipe)"
                          : " (individual)"}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Documento (opcional) */}
            {selectedCategoryId && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Documento (CPF, RG ou passaporte — opcional)
                </label>
                <Input
                  value={document}
                  onChange={(e) => setDocument(e.target.value)}
                  placeholder="000.000.000-00"
                  maxLength={30}
                />
              </div>
            )}

            {/* Box / Centro de Treinamento (opcional) */}
            {selectedCategoryId && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Box / Centro de Treinamento (opcional)
                </label>
                <Input
                  value={boxName}
                  onChange={(e) => setBoxName(e.target.value)}
                  placeholder="Ex: CrossFit Oceania"
                  maxLength={200}
                />
              </div>
            )}

            {/* Campos de equipe */}
            {isTeam && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nome da Equipe
                  </label>
                  <Input
                    value={teamName}
                    onChange={(e) => setTeamName(e.target.value)}
                    placeholder="Ex: Dupla Furiosa"
                    required
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      Outros Membros
                      {selectedCategory?.max_team_size && (
                        <span className="text-gray-400 font-normal ml-1">
                          (até {maxAdditional} além de você)
                        </span>
                      )}
                    </label>
                    {additionalMembers.length < maxAdditional && (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={addMember}
                      >
                        <PlusIcon className="h-4 w-4 mr-1" />
                        Adicionar membro
                      </Button>
                    )}
                  </div>

                  {additionalMembers.length === 0 ? (
                    <p className="text-sm text-gray-400">
                      Nenhum membro adicional. Clique em "Adicionar membro" para incluir outros participantes.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {additionalMembers.map((member, index) => (
                        <div
                          key={index}
                          className="flex gap-2 items-start p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="flex-1 grid grid-cols-2 gap-2">
                            <Input
                              value={member.full_name}
                              onChange={(e) => updateMember(index, "full_name", e.target.value)}
                              placeholder="Nome completo"
                              required
                            />
                            <Input
                              type="email"
                              value={member.email}
                              onChange={(e) => updateMember(index, "email", e.target.value)}
                              placeholder="email@exemplo.com"
                              required
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => removeMember(index)}
                            className="mt-1 text-gray-400 hover:text-red-500 transition-colors"
                            aria-label="Remover membro"
                          >
                            <TrashIcon className="h-5 w-5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}

            {/* Aceite do termo de consentimento — só aparece se a competição tiver um termo */}
            {selectedCategoryId && consentTerm?.has_term && selectedCompetitionId && (
              <div className="flex items-start gap-2">
                <input
                  id="consent-accepted"
                  type="checkbox"
                  checked={consentAccepted}
                  onChange={(e) => setConsentAccepted(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <label htmlFor="consent-accepted" className="text-sm text-gray-700">
                  Li e concordo com o{" "}
                  <a
                    href={consentTermApi.fileUrl(selectedCompetitionId)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-600 underline font-medium"
                  >
                    termo de consentimento
                  </a>
                </label>
              </div>
            )}

            {selectedCategoryId && (
              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full"
                  isLoading={loading}
                  disabled={Boolean(consentTerm?.has_term) && !consentAccepted}
                >
                  Confirmar Inscrição
                </Button>
              </div>
            )}
          </form>
        </Card>
      )}
    </div>
  );
}
