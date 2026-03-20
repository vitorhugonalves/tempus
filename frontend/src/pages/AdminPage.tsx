import { useEffect, useRef, useState } from "react";
import { adminApi, type BoxSettingsData, type BoxSettingsUpdate } from "../api/admin";
import { Card } from "../components/ui/Card";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Alert from "../components/ui/Alert";

export default function AdminPage() {
  const [settings, setSettings] = useState<BoxSettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [logoTimestamp, setLogoTimestamp] = useState(Date.now());

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [website, setWebsite] = useState("");
  const [instagram, setInstagram] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    adminApi
      .getSettings()
      .then(({ data }) => {
        setSettings(data);
        setName(data.name ?? "");
        setAddress(data.address ?? "");
        setWebsite(data.website ?? "");
        setInstagram(data.instagram ?? "");
      })
      .catch(() => setError("Erro ao carregar configurações."))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: BoxSettingsUpdate = {
        name: name || undefined,
        address: address || null,
        website: website || null,
        instagram: instagram || null,
      };
      const { data } = await adminApi.updateSettings(payload);
      setSettings(data);
      setSuccess("Configurações salvas com sucesso.");
    } catch {
      setError("Erro ao salvar configurações.");
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const { data } = await adminApi.uploadLogo(file);
      setSettings(data);
      setLogoTimestamp(Date.now());
      setSuccess("Logotipo atualizado com sucesso.");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Erro ao fazer upload do logotipo.");
    } finally {
      setLogoUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-400 text-sm">Carregando...</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Administração</h1>
        <p className="text-gray-500 text-sm mt-1">
          Configure os dados e logotipo do Box / Centro de Treinamento.
        </p>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {/* Dados do Box */}
      <Card>
        <h2 className="text-base font-semibold text-gray-900 mb-4">Dados do Box</h2>
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Nome do Box / Centro de Treinamento
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex: CrossFit Oceania"
              maxLength={200}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Endereço (opcional)
            </label>
            <Input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Ex: Rua das Olimpíadas, 100 — São Paulo / SP"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Site (opcional)
            </label>
            <Input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="Ex: https://www.seucrossfit.com.br"
              maxLength={500}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Instagram (opcional)
            </label>
            <Input
              value={instagram}
              onChange={(e) => setInstagram(e.target.value)}
              placeholder="Ex: @seucrossfit"
              maxLength={200}
            />
          </div>

          <div className="pt-2">
            <Button type="submit" variant="primary" isLoading={saving}>
              Salvar Dados
            </Button>
          </div>
        </form>
      </Card>

      {/* Logotipo */}
      <Card>
        <h2 className="text-base font-semibold text-gray-900 mb-4">Logotipo</h2>
        <p className="text-sm text-gray-500 mb-4">
          O logotipo é exibido na página inicial, no ranking e nos relatórios PDF.
          Formatos aceitos: PNG, JPEG, GIF, WebP. Tamanho máximo: 5 MB.
        </p>

        {settings?.has_logo && (
          <div className="mb-4 p-4 bg-gray-50 rounded-lg flex items-center justify-center">
            <img
              src={`${adminApi.getLogoUrl()}?t=${logoTimestamp}`}
              alt="Logotipo atual"
              className="max-h-24 max-w-full object-contain"
            />
          </div>
        )}

        {!settings?.has_logo && (
          <div className="mb-4 p-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 text-center">
            <p className="text-sm text-gray-400">Nenhum logotipo configurado.</p>
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            isLoading={logoUploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {settings?.has_logo ? "Trocar Logotipo" : "Enviar Logotipo"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            className="hidden"
            onChange={handleLogoUpload}
          />
        </div>
      </Card>
    </div>
  );
}
