type SearchPerson = { name: string | null; email: string | null; relationship: "connected" | "available" };

function relevance(person: SearchPerson, query: string) {
  const normalize = (value: string) => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().replace(/\s+/g, " ");
  const term = normalize(query);
  const name = normalize(person.name || "");
  const email = normalize(person.email || "");
  if (!term) return 0;
  if (name === term) return 5;
  if (name.startsWith(term)) return 4 + term.length / name.length;
  if (name.split(" ").some(part => part.startsWith(term))) return 3 + term.length / name.length;
  if (name.includes(term)) return 2 + term.length / name.length;
  if (term.split(" ").every(part => name.includes(part))) return 1.5;
  if (email.includes(term)) return 1;
  return 0;
}

export function groupClientSearchResults<T extends SearchPerson>(people: T[], query: string) {
  return (["connected", "available"] as const).map(relationship => {
    const members = people.filter(person => person.relationship === relationship)
      .map(person => ({ person, score: relevance(person, query) }))
      .sort((a, b) => b.score - a.score);
    return { relationship, people: members.map(member => member.person), score: members[0]?.score ?? -1 };
  }).filter(group => group.people.length > 0).sort((a, b) => b.score - a.score);
}
