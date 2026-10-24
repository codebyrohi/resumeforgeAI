// Mirrors backend app/schemas.py `Profile` - the one JSON document both exports render from.
export const emptyProfile = () => ({
  basics: { full_name: "", headline: "", email: "", phone: "", location: "" },
  summary: "",
  education: [],
  experience: [],
  projects: [],
  skills: [],
  links: [],
});

export const blank = {
  education: () => ({ institution: "", degree: "", field: "", start: "", end: "", grade: "", details: "" }),
  experience: () => ({ company: "", title: "", location: "", start: "", end: "", bullets: [] }),
  projects: () => ({ name: "", description: "", tech: [], url: "" }),
  links: () => ({ label: "", url: "" }),
};
