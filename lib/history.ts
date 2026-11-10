// Sunucu tarafı erişim. data/history.json büyüktür; bu modülü yalnızca
// rota işleyicileri ve diğer sunucu kodları içe aktarmalıdır.
import history from '../data/history.json';
import kapUniverse from '../data/kap-universe.json';
import type { HistoryCompany, HistoryResponse } from './history-fields';

type HistoryFile = {
  source: string;
  collectedAt: string;
  unit: string;
  periodOrder: string[];
  note: string;
  companies: Record<string, HistoryCompany>;
};

const file = history as unknown as HistoryFile;
const companies = new Map(Object.entries(file.companies ?? {}));

export const codePattern = /^[A-Z0-9]{3,6}$/;

/** Aynı ihraççının diğer pay kodları (ör. A/B/C grubu paylar). */
function siblingCodes(code: string): string[] {
  const issuer = kapUniverse.companies.find(company => company.codes.includes(code));
  return issuer ? issuer.codes.filter(other => other !== code) : [];
}

export function getHistory(requestedCode: string): HistoryResponse | null {
  if (!codePattern.test(requestedCode)) return null;
  const code = [requestedCode, ...siblingCodes(requestedCode)].find(candidate => companies.has(candidate));
  if (!code) return null;
  return {
    code,
    requestedCode,
    unit: file.unit,
    note: file.note,
    source: file.source,
    collectedAt: file.collectedAt,
    company: companies.get(code)!,
  };
}
