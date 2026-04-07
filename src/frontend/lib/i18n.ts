import pt from "@/locales/pt.json";

/**
 * Acede a uma traducao por chave dot-separated.
 * Ex: t("auth.login.title") → "Entrar"
 */
export function t(key: string): string {
  const keys = key.split(".");
  let value: unknown = pt;
  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = (value as Record<string, unknown>)[k];
    } else {
      return key;
    }
  }
  return typeof value === "string" ? value : key;
}
