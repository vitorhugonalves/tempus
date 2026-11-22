interface CategorizedEntry {
  category_name: string | null;
}

/**
 * Indica se a linha `index` abre um novo grupo de categoria.
 *
 * O backend já entrega o ranking geral ordenado por categoria; basta comparar
 * com a linha anterior para saber onde desenhar o cabeçalho do grupo.
 */
export function startsCategoryGroup(entries: CategorizedEntry[], index: number): boolean {
  if (index < 0 || index >= entries.length) return false;
  if (index === 0) return true;
  return entries[index].category_name !== entries[index - 1].category_name;
}
