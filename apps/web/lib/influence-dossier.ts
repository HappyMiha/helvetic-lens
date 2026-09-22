import type { InfluenceDossier } from "./influence-graph";

/** Curated public-source snapshot. Do not turn this into a store for private data. */
export const influenceDossier: InfluenceDossier = {
  id: "blocher-ems-neutrality-2026-09-22",
  title: "Christoph Blocher · EMS · Neutralitätsinitiative",
  checkedOn: "2026-09-22",
  summaryLanguage: "en",
  sources: [
    {
      id: "ems-finance-2025",
      title: "EMS Group · Finance Report 2025",
      publisher: "EMS Group",
      url: "https://www.ems-group.com/fileadmin/user_upload/EMS-Group/news/2026/2026-03-24_Finanzbericht/EMS_Group_Finance_Report_2025_684152.pdf",
      kind: "primary_corporate",
      language: "en",
      publishedOn: "2026-03-24",
      checkedOn: "2026-09-22",
    },
    {
      id: "ems-biography",
      title: "Magdalena Martullo-Blocher · Corporate biography",
      publisher: "EMS Group",
      url: "https://www.ems-group.com/en/investors/corporate-governance/board-of-directors/magdalena-martullo-blocher/",
      kind: "primary_corporate",
      language: "en",
      publishedOn: null,
      checkedOn: "2026-09-22",
    },
    {
      id: "initiative-committee",
      title: "Abstimmungskomitee",
      publisher: "Neutralität Ja",
      url: "https://neutralitaet-ja.ch/abstimmungskomitee/",
      kind: "primary_campaign",
      language: "de",
      publishedOn: null,
      checkedOn: "2026-09-22",
    },
    {
      id: "fdfa-neutrality",
      title: "Neutrality Initiative",
      publisher: "FDFA / EDA",
      url: "https://www.eda.admin.ch/en/neutrality",
      kind: "primary_government",
      language: "en",
      publishedOn: "2026-09-01",
      checkedOn: "2026-09-22",
    },
    {
      id: "republik-investigation",
      title: "Die Geschäfte der Blochers in Russland",
      publisher: "Republik · Lukas Häuptli, Fabian Kohler",
      url: "https://www.republik.ch/2026/09/04/die-geschaefte-der-blochers-in-russland",
      kind: "reporting",
      language: "de",
      publishedOn: "2026-09-04",
      checkedOn: "2026-09-22",
    },
    {
      id: "ems-response",
      title: "Dementi zu Blick Online vom 17.9.26",
      publisher: "EMS Group",
      url: "https://www.ems-group.com/de/medien/finanz-medienmitteilungen/ems-gruppe/detail/dementi-der-ems-chemie-zu-falscher-berichterstattung-von-blick-online-am-17926/",
      kind: "primary_corporate",
      language: "de",
      publishedOn: "2026-09-17",
      checkedOn: "2026-09-22",
    },
  ],
  entities: [
    {
      id: "blocher",
      name: "Christoph Blocher",
      kind: "person",
      country: "CH",
      x: 30,
      y: 30,
    },
    {
      id: "initiative",
      name: "Neutralitätsinitiative",
      kind: "initiative",
      country: "CH",
      x: 360,
      y: 30,
    },
    {
      id: "sanctions",
      name: "Swiss sanctions framework",
      kind: "policy",
      country: "CH",
      x: 690,
      y: 30,
    },
    {
      id: "magdalena",
      name: "Magdalena Martullo-Blocher",
      kind: "person",
      country: "CH",
      x: 30,
      y: 200,
    },
    {
      id: "emesta",
      name: "Emesta Holding AG",
      kind: "company",
      country: "CH",
      x: 30,
      y: 370,
    },
    {
      id: "mamira",
      name: "Mamira Holding AG",
      kind: "company",
      country: "CH",
      x: 30,
      y: 540,
    },
    {
      id: "baumi",
      name: "BAUMI Holding AG",
      kind: "company",
      country: "CH",
      x: 30,
      y: 710,
    },
    {
      id: "ems",
      name: "EMS Group",
      kind: "group",
      country: "CH",
      x: 360,
      y: 370,
    },
    {
      id: "elabuga",
      name: "EFTEC (Elabuga) OOO",
      kind: "company",
      country: "RU",
      x: 690,
      y: 200,
    },
    {
      id: "novgorod",
      name: "EFTEC (Nizhniy Novgorod) OOO",
      kind: "company",
      country: "RU",
      x: 690,
      y: 370,
    },
    {
      id: "customers",
      name: "KAMAZ · GAZ · UAZ · AvtoVAZ",
      kind: "group",
      country: "RU",
      x: 690,
      y: 710,
    },
    {
      id: "shareholders",
      name: "EMS-CHEMIE HOLDING AG shareholders (aggregate)",
      kind: "group",
      country: null,
      x: 360,
      y: 710,
    },
  ],
  edges: [
    {
      id: "E01",
      from: "blocher",
      to: "initiative",
      kind: "campaign",
      status: "documented",
      label: "Campaign committee",
      asOf: "2026-09-22",
      statement:
        "The campaign lists Christoph Blocher as a member of its main committee.",
      supporting: [
        {
          sourceId: "initiative-committee",
          locator: "Hauptkomitee · Christoph Blocher",
          summary: "The campaign's own committee page includes his name.",
        },
      ],
      disputing: [],
      limits: [
        "Committee membership does not establish a donation amount or a motive.",
      ],
    },
    {
      id: "E02",
      from: "blocher",
      to: "magdalena",
      kind: "family",
      status: "documented",
      label: "Father → daughter",
      asOf: null,
      statement:
        "EMS identifies Magdalena Martullo-Blocher as the daughter of its former owner, Christoph Blocher.",
      supporting: [
        {
          sourceId: "ems-biography",
          locator: "Professional career",
          summary:
            "The biography describes her father's election to the Federal Council and sale of his shares to his children.",
        },
      ],
      disputing: [],
      limits: [
        "Family ties do not establish current ownership or payments to Christoph Blocher.",
      ],
    },
    {
      id: "E03",
      from: "magdalena",
      to: "ems",
      kind: "role",
      status: "documented",
      label: "Chief executive",
      asOf: "2026-09-22",
      statement:
        "EMS lists Magdalena Martullo-Blocher as CEO and executive vice-chair of the board.",
      supporting: [
        {
          sourceId: "ems-biography",
          locator: "Position / Professional career",
          summary: "The corporate biography identifies both executive roles.",
        },
      ],
      disputing: [],
      limits: [
        "A management role is not a record of an individual financial transfer.",
      ],
    },
    ...(
      [
        ["E04", "emesta", "30.41"],
        ["E05", "mamira", "30.41"],
        ["E06", "baumi", "10.10"],
      ] as const
    ).map(([id, from, percentage]) => ({
      id,
      from,
      to: "ems",
      kind: "ownership" as const,
      status: "documented" as const,
      label: `${percentage}% shareholding`,
      asOf: "2025-12-31",
      statement: `${percentage}% of EMS-CHEMIE HOLDING AG reported at year-end 2025.`,
      supporting: [
        {
          sourceId: "ems-finance-2025",
          locator: "Note 19 · printed p. 23/36 · PDF page 26",
          summary: `Reported shareholding: ${percentage}%.`,
        },
      ],
      disputing: [],
      limits: [
        "Dated holding; not a payment record or a claim about today's ultimate beneficiary.",
      ],
    })),
    ...(
      [
        ["E07", "elabuga"],
        ["E08", "novgorod"],
      ] as const
    ).map(([id, to]) => ({
      id,
      from: "ems",
      to,
      kind: "ownership" as const,
      status: "documented" as const,
      label: "100% group ownership",
      asOf: "2025-12-31",
      statement:
        "EMS reports 100% ownership of this Russian subsidiary at year-end 2025.",
      supporting: [
        {
          sourceId: "ems-finance-2025",
          locator: "Note 32 · printed p. 32/36 · PDF page 35",
          summary: "Subsidiary listed in Russia with 100.00% ownership.",
        },
      ],
      disputing: [],
      limits: [
        "Consolidated group ownership; the intermediate legal-parent chain is not established here.",
      ],
    })),
    {
      id: "E09",
      from: "ems",
      to: "customers",
      kind: "business",
      status: "disputed",
      label: "Reported EFTEC customer links",
      asOf: null,
      statement:
        "Republik reports indications of sales by Russian EFTEC operations to these four companies. The defence-business allegation is disputed by EMS.",
      supporting: [
        {
          sourceId: "republik-investigation",
          locator:
            "Investigation · customer-list and company-document discussion",
          summary:
            "The reporters describe former customer listings and other records suggesting business relationships.",
        },
      ],
      disputing: [
        {
          sourceId: "ems-response",
          locator: "Statement dated 17 September 2026",
          summary:
            "Responding to Blick Online, EMS denies trading with sanctioned defence companies and says it is not in the defence business.",
        },
      ],
      limits: [
        "No invoice, bank transfer, signed contract or underlying customs record has been independently retained for this dossier.",
        "The grouped display does not establish which EFTEC legal entity supplied which customer, on what dates, or whether any transaction breached sanctions.",
      ],
    },
    {
      id: "E10",
      from: "initiative",
      to: "sanctions",
      kind: "policy_proposal",
      status: "documented",
      label: "Proposed sanctions restriction",
      asOf: "2026-09-01",
      statement:
        "The initiative proposes restricting sanctions against belligerent states, with exceptions for UN sanctions and anti-circumvention measures.",
      supporting: [
        {
          sourceId: "fdfa-neutrality",
          locator: "Aim of the initiative / Sanctions FAQ",
          summary:
            "The FDFA describes the proposed rule and the scheduled vote on 27 September 2026. This is a proposal in this snapshot, not enacted law.",
        },
      ],
      disputing: [],
      limits: [
        "The FDFA represents the Federal Council, which opposes the initiative. Its explanation is attributed; the graph does not predict the vote or future implementation.",
      ],
    },
    {
      id: "E11",
      from: "sanctions",
      to: "ems",
      kind: "potential_impact",
      status: "not_established",
      label: "Possible economic effect",
      asOf: null,
      statement:
        "A change in the sanctions framework could affect the legal environment for Russia-related business. An economic benefit to EMS is not established here.",
      supporting: [
        {
          sourceId: "fdfa-neutrality",
          locator: "Sanctions FAQ",
          summary:
            "The FDFA discusses possible changes to sanctions if the initiative is accepted; it does not identify an EMS financial benefit.",
        },
      ],
      disputing: [
        {
          sourceId: "ems-response",
          locator: "Final paragraph",
          summary:
            "EMS says the initiative is not relevant to its business and Russia accounts for less than 1% of group turnover.",
        },
      ],
      limits: [
        "Analytical question, not a proven effect, financial valuation or attribution of political motive.",
      ],
    },
    {
      id: "E12",
      from: "ems",
      to: "shareholders",
      kind: "dividend",
      status: "documented",
      label: "Dividends paid · 2025",
      asOf: "2025-12-31",
      statement:
        "EMS reports CHF 403,461,000 paid to shareholders of EMS-CHEMIE HOLDING AG in 2025.",
      supporting: [
        {
          sourceId: "ems-finance-2025",
          locator: "Cash flows · printed p. 5/36 · PDF page 8",
          summary:
            "Dividend cash outflow of 403,461 in the table's CHF thousands unit.",
        },
      ],
      disputing: [],
      limits: [
        "Group-wide aggregate; not attributed to Russia, a particular shareholder, or Christoph Blocher.",
      ],
      money: {
        amount: 403461000,
        currency: "CHF",
        periodStart: "2025-01-01",
        periodEnd: "2025-12-31",
        basis: "paid",
        evidenceSourceId: "ems-finance-2025",
      },
    },
  ],
  gaps: [
    "This dossier does not establish that Christoph Blocher personally receives money from Russian military companies.",
    "No verified campaign-donation record is included. Committee membership is the only campaign connection shown.",
    "No traced payment chain from Russian customers through EFTEC and EMS to a named individual is included.",
  ],
};
