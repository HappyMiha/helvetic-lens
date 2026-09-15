"""Assert fixed HTTP configuration reads separately from page query budgets."""

import re
from collections import Counter

CONFIGURATION_TABLES = (
    "apertus_configuration",
    "prompt_configuration",
    "platform_prompt_configuration",
    "monitoring_connector_configurations",
)


def page_queries(queries):
    configuration_reads, page = Counter(), []
    for query in queries:
        tables = [table for table in CONFIGURATION_TABLES
            if re.search(r'\bFROM\s+"?' + table + r'"?(?=\s|$)', query, re.IGNORECASE)]
        if tables:
            # Do not hide a combined/subquery read inside request setup.
            assert len(tables) == 1 and len(re.findall(r"\bFROM\b", query, re.IGNORECASE)) == 1
            assert not re.search(r"\bJOIN\b", query, re.IGNORECASE)
            configuration_reads.update(tables)
        else:
            page.append(query)
    # Missing, repeated or per-row configuration loads are regressions too.
    assert configuration_reads == Counter(CONFIGURATION_TABLES), configuration_reads
    return page
