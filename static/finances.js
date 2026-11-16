"use strict";
// Chiffrage (deux modes), budget et attentes du client. Les calculs viennent du serveur (finances.py).
const FINANCES = "Finances";
const euros = v => (v == null ? "—" : Math.round(v).toLocaleString("fr-FR") + " €");
const jours = v => (v == null ? "—" : (Math.round(v * 10) / 10).toLocaleString("fr-FR") + " j");
const pourcent = v => (v == null ? "—" : Math.round(v * 100) + " %");
const MODES = { macro: ["Macro", "avant la collecte d'informations : taille et abaque"],
  detaille: ["Détaillé", "après la collecte : charge en trois points par profil"] };

// ---------- Chiffrage ----------
VUES.chiffrage = ["Chiffrage", FINANCES, async v => {
  const c = await api("GET", "chiffrage"), p = c.parametres;
  const mode = etat.modeChiffrage && MODES[etat.modeChiffrage] ? etat.modeChiffrage : p.mode_retenu;
  const m = c.modes[mode];
  v.append(titreVue("Chiffrage",
    "Deux modes qui coexistent : un chiffrage macro quand on sait peu de choses, puis un chiffrage détaillé après les ateliers. La comparaison par lot montre ce que la collecte a changé ; le mode retenu alimente le budget.",
    el("button", { onclick: () => dialogueParametres(p, c.tjm_moyen) }, "Paramètres"),
    boutonAjout("estimation", "Ajouter un élément", { mode, confiance: mode === "macro" ? "moyenne" : "" })));

  v.append(el("div", { class: "barre", role: "tablist" }, Object.entries(MODES).map(([cle, [lib, sous]]) =>
    el("button", { role: "tab", "aria-selected": cle === mode ? "true" : "false", class: cle === mode ? "principal" : "",
      title: sous, onclick: () => { etat.modeChiffrage = cle; recharger(); } },
      `${lib} (${c.modes[cle].nb})`, cle === p.mode_retenu ? " · retenu" : "")),
    el("span", { class: "pousse" }),
    mode !== p.mode_retenu && el("button", { onclick: async e => pendant(e.target, "…", async () => {
      await api("PUT", "mission", { chiffrage: { ...p, mode_retenu: mode } }); dire("Mode retenu : " + MODES[mode][0] + "."); await recharger();
    }) }, "Retenir ce chiffrage"),
    m.montant != null && el("button", { title: "Fixe le budget vendu à ce montant (modifiable dans la vue Budget)", onclick: async e => {
      if (!confirm(`Reporter ${euros(m.montant)} comme budget vendu ?`)) return;
      await pendant(e.target, "…", async () => { await api("PUT", "mission", { budget_vendu: Math.round(m.montant) }); dire("Budget vendu mis à jour."); });
    } }, "Reporter en budget vendu")));
  v.append(el("p", { class: "aide" }, `${MODES[mode][0]} : ${MODES[mode][1]}.`));

  if (!m.nb) {
    v.append(el("div", { class: "vide" }, mode === "detaille" && c.modes.macro.nb
      ? [el("p", { style: "margin:0 0 10px" }, "Aucun élément détaillé. Partez du macro : une ligne par élément, à répartir ensuite par profil."),
        el("button", { class: "principal", onclick: async e => pendant(e.target, "…", async () => {
          await api("POST", "estimation/depuis_macro"); await recharger(); dire("Chiffrage détaillé initialisé depuis le macro.");
        }) }, "Initialiser depuis le macro")]
      : "Aucun élément chiffré dans ce mode."));
  } else {
    const t = m.total_jours, maj = Math.round(c.taux_majoration * 100);
    v.append(el("div", { class: "grille" },
      tuile("Charge de base", jours(m.base.retenu), `fourchette ${jours(m.base.bas)} à ${jours(m.base.haut)}`),
      tuile(`Majorations (+${maj} %)`, jours(t.retenu - m.base.retenu), Object.entries(m.majorations).map(([k, x]) => `${{ qualite: "qualité" }[k] || k} ${jours(x)}`).join(" · ")),
      tuile("Charge totale", jours(t.retenu), `fourchette ${jours(t.bas)} à ${jours(t.haut)}`),
      tuile("Montant", euros(m.montant), `fourchette ${euros(m.montant_bas)} à ${euros(m.montant_haut)}`),
      tuile("TJM moyen", euros(c.tjm_moyen), m.sans_valorisation ? `${m.sans_valorisation} ligne(s) sans TJM` : "profils de la vue Budget")));
    const cols = mode === "macro"
      ? [["Lot", l => pastilleLot(l.lot)], ["Élément", l => [el("b", {}, l.libelle), l.hypothese && el("div", { style: "color:var(--doux);font-size:13px" }, l.hypothese)], "long"],
        ["Taille", l => l.taille || (l.jours_probable != null ? "saisie" : pastille("orange", "à dimensionner"))], ["Confiance", l => l.confiance || "moyenne"],
        ["Bas", l => jours(l.bas), "num"], ["Retenu", l => el("b", {}, jours(l.retenu)), "num"], ["Haut", l => jours(l.haut), "num"], ["Montant", l => euros(l.montant), "num"]]
      : [["Lot", l => pastilleLot(l.lot)], ["Élément", l => [el("b", {}, l.libelle), l.hypothese && el("div", { style: "color:var(--doux);font-size:13px" }, l.hypothese)], "long"],
        ["Profil", l => l.profil || pastille("orange", "à affecter")], ["Bas", l => jours(l.bas), "num"], ["Probable", l => jours(l.jours_probable), "num"],
        ["Haut", l => jours(l.haut), "num"], ["PERT", l => el("b", {}, jours(l.retenu)), "num"], ["Montant", l => euros(l.montant), "num"]];
    v.append(el("h3", {}, "Éléments chiffrés"), tableau("estimation", m.lignes, cols, recharger));
  }

  if (c.comparaison.length && c.modes.macro.nb && c.modes.detaille.nb) {
    v.append(el("h3", {}, "Macro et détaillé, par lot (charge de base)"), el("div", { class: "cadre-table" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Lot", "Macro", "Détaillé", "Écart"].map(x => el("th", {}, x)))),
      el("tbody", {}, c.comparaison.map(l => el("tr", {},
        el("td", {}, pastilleLot(l.lot)), el("td", { class: "num" }, jours(l.macro)), el("td", { class: "num" }, l.detaille ? jours(l.detaille) : "non détaillé"),
        el("td", {}, l.ecart == null ? "—" : pastille(Math.abs(l.ecart) > 0.2 ? "orange" : "vert", (l.ecart > 0 ? "+" : "") + Math.round(l.ecart * 100) + " %"))))))));
  }
}];

function dialogueParametres(p, tjmCalcule) {
  const d = $("#dialogue"), s = {};
  const champ = (groupe, cle, lib, facteur = 1) => {
    const i = el("input", { type: "number", step: "any" });
    const val = groupe ? p[groupe][cle] : p[cle];
    i.value = val == null ? "" : Math.round(val * facteur * 100) / 100;
    s[(groupe || "") + "." + cle] = [i, groupe, cle, facteur];
    return el("label", {}, lib, i);
  };
  d.replaceChildren(el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    const n = JSON.parse(JSON.stringify(p));
    for (const [i, groupe, cle, facteur] of Object.values(s)) {
      const val = i.value === "" ? null : Number(i.value) / facteur;
      if (groupe) n[groupe][cle] = val; else n[cle] = val;
    }
    try { await api("PUT", "mission", { chiffrage: n }); d.close(); await recharger(); dire("Paramètres du chiffrage enregistrés."); }
    catch (err) { dire(err.message, true); }
  } },
    el("h3", {}, "Paramètres du chiffrage"),
    el("p", { class: "aide", style: "margin:0" }, "Abaque du mode macro (jours par taille), largeur de la fourchette selon la confiance, majorations appliquées aux deux modes."),
    el("div", { class: "champs" },
      ["XS", "S", "M", "L", "XL"].map(t => champ("abaque", t, `Taille ${t} (jours)`)),
      champ("marges", "forte", "Confiance forte : ± %", 100), champ("marges", "moyenne", "Confiance moyenne : ± %", 100),
      champ("marges", "faible", "Confiance faible : ± %", 100),
      champ("majorations", "pilotage", "Pilotage (%)", 100), champ("majorations", "qualite", "Qualité et recette (%)", 100),
      champ("majorations", "contingence", "Contingence (%)", 100),
      el("label", { class: "large" }, `TJM moyen du macro (€) — vide : moyenne des profils (${euros(tjmCalcule)})`,
        (() => { const i = el("input", { type: "number", step: "any" }); i.value = p.tjm_moyen ?? ""; s[".tjm_moyen"] = [i, null, "tjm_moyen", 1]; return i; })())),
    el("div", { class: "barre" }, el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Annuler"), el("button", { class: "principal" }, "Enregistrer"))));
  d.showModal();
}

// ---------- Budget ----------
VUES.budget = ["Budget", FINANCES, async v => {
  const [b, consommations, depenses, factures] = await Promise.all(
    [api("GET", "budget"), api("GET", "consommation"), api("GET", "depense"), api("GET", "facture")]);
  v.append(titreVue("Budget",
    "Vendu, consommé, reste à faire et atterrissage, valorisés aux TJM des profils ; dépenses et échéancier de facturation. Le reste à faire en jours se met à jour sur chaque profil.",
    el("button", { onclick: () => dialogueBudgetVendu(b.vendu) }, "Budget vendu")));
  const ref_ = b.reference;
  v.append(el("div", { class: "grille" },
    tuile(b.reference_source === "vendu" ? "Budget vendu" : "Budget chiffré (non vendu)", euros(ref_),
      b.reference_source === "vendu" ? "" : "Renseignez le budget vendu"),
    tuile("Consommé", euros(b.consomme), `${pourcent(b.taux_consomme)} du budget · avancement ${pourcent(b.avancement)}`),
    tuile("Reste à faire", euros(b.raf), b.depenses_prevues ? `dont ${euros(b.depenses_prevues)} de dépenses prévues` : ""),
    tuile("Atterrissage", euros(b.atterrissage), b.ecart == null ? "" : [pastille(b.ecart < 0 ? "rouge" : "vert", (b.ecart < 0 ? "Dépassement " : "Marge de manœuvre ") + euros(Math.abs(b.ecart)))]),
    tuile("Marge prévue", euros(b.marge), b.taux_marge == null ? "coûts journaliers à compléter" : pourcent(b.taux_marge) + " du budget"),
    tuile("Facturé", euros(b.facture), `payé ${euros(b.paye)} · reste ${euros(b.a_facturer)}`)));
  if (b.alertes.length) v.append(el("h3", {}, "Alertes"), el("div", { class: "liste" }, b.alertes.map(x => el("div", { class: "item" },
    el("div", { class: "tete" }, pastille(x.niveau >= 3 ? "rouge" : "orange", x.niveau >= 3 ? "Niveau 3 — sponsor" : "Niveau 2 — projet"), el("span", { class: "titre" }, x.titre)),
    el("div", { class: "detail" }, x.detail)))));
  if (b.par_mois.length) {
    v.append(el("h3", {}, "Consommation"), el("div", { class: "graphes" }, graphe({
      titre: "Consommé par mois et cumul", sous: "En euros, valorisé aux TJM ; la ligne pointillée est le budget de référence.",
      categories: b.par_mois.map(x => { const [a, mm] = x.mois.split("-"); return `${MOIS[+mm - 1]} ${a.slice(2)}`; }),
      series: [{ nom: "Mois", couleur: C1_CLAIR, type: "barre", valeurs: b.par_mois.map(x => x.montant) },
        { nom: "Cumul", couleur: C1, type: "ligne", valeurs: b.par_mois.map(x => x.cumul) }],
      seuil: ref_ ? { valeur: ref_, libelle: "Budget" } : null, suffixe: " €", legendeForcee: true })));
  }
  v.append(section("Profils et TJM", "profil", b.par_profil, [
    ["Profil", l => el("b", {}, l.nom)], ["TJM", l => euros(l.tjm), "num"], ["Coût / j", l => euros(l.cout_journalier), "num"],
    ["Consommé", l => jours(l.consomme_jours), "num"], ["Reste à faire", l => jours(l.raf_jours), "num"],
    ["Atterrissage", l => jours(l.atterrissage_jours), "num"], ["Montant", l => euros(l.atterrissage), "num"]], recharger));
  v.append(section("Temps consommés", "consommation", [...consommations].reverse(), [
    ["Mois", l => l.mois || "—"], ["Profil", l => l.profil || "—"], ["Jours", l => jours(l.jours), "num"],
    ["Montant", l => euros((l.jours || 0) * (ref.profils.find(p => p.nom === l.profil)?.tjm || 0)), "num"], ["Commentaire", l => l.commentaire || "", "long"]], recharger));
  v.append(section("Dépenses hors temps passé", "depense", depenses, [
    ["Dépense", l => l.libelle, "long"], ["Catégorie", l => l.categorie || "—"], ["Date", l => dateFr(l.date)],
    ["Montant", l => euros(l.montant), "num"], ["Statut", l => pastille(l.statut === "payée" ? "vert" : l.statut === "engagée" ? "neutre" : "orange", l.statut || "prévue")]], recharger));
  const auj = new Date().toISOString().slice(0, 10);
  v.append(section("Échéancier de facturation", "facture", factures, [
    ["Échéance", l => l.libelle, "long"], ["Jalon", l => l.jalon || "—"], ["Date prévue", l => dateFr(l.date_prevue)],
    ["Montant", l => euros(l.montant), "num"],
    ["Statut", l => [pastille(l.statut === "payée" ? "vert" : l.statut === "facturée" ? "neutre" : "orange", l.statut || "à facturer"),
      (l.statut || "à facturer") === "à facturer" && l.date_prevue && l.date_prevue < auj ? [" ", pastille("rouge", "En retard")] : null]]], recharger));
}];

function dialogueBudgetVendu(valeur) {
  const d = $("#dialogue"), i = el("input", { type: "number", step: "any" });
  i.value = valeur ?? "";
  d.replaceChildren(el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    try { await api("PUT", "mission", { budget_vendu: i.value === "" ? null : Number(i.value) }); d.close(); await recharger(); dire("Budget vendu enregistré."); }
    catch (err) { dire(err.message, true); }
  } }, el("h3", {}, "Budget vendu"),
    el("label", {}, "Montant vendu au client (€, hors taxes) — vide : le chiffrage retenu sert de référence", i),
    el("div", { class: "barre" }, el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Annuler"), el("button", { class: "principal" }, "Enregistrer"))));
  d.showModal();
}

// ---------- Attentes du client ----------
const POSITIONS = { "alignée": "vert", "à recadrer": "orange", "hors périmètre": "neutre" };
const satisfaction = s => (s == null ? "—" : pastille(s <= 2 ? "rouge" : s === 3 ? "orange" : "vert", s + " / 5"));
VUES.attentes = ["Attentes du client", PILOTAGE, async v => {
  const r = await api("GET", "suivi_attentes"), liste = r.attentes;
  v.append(titreVue("Attentes du client",
    "Ce que chaque partie prenante attend, notre réponse, et la satisfaction perçue. L'évolution est calculée depuis le précédent changement de satisfaction (historique). Une attente se recadre explicitement : position « à recadrer » et prochaine action.",
    boutonAjout("attente", "Ajouter une attente", { position: "alignée", priorite: 2, revue_le: new Date().toISOString().slice(0, 10) })));
  if (!liste.length) { v.append(el("div", { class: "vide" }, "Aucune attente suivie.")); return; }
  const prioInsat = liste.filter(x => x.priorite === 1 && x.satisfaction != null && x.satisfaction <= 2).length;
  v.append(el("div", { class: "grille" },
    tuile("Attentes suivies", nb(liste.length), `${new Set(liste.map(x => x.partie_prenante)).size} partie(s) prenante(s)`),
    tuile("Prioritaires insatisfaites", nb(prioInsat), "satisfaction ≤ 2 sur une priorité 1"),
    tuile("À recadrer", nb(liste.filter(x => x.position === "à recadrer").length)),
    tuile("Revues à faire", nb(liste.filter(x => x.revue_due).length), "dernière revue de plus de 30 jours")));
  if (r.alertes.length) v.append(el("h3", {}, "Alertes"), el("div", { class: "liste" }, r.alertes.map(x => el("div", { class: "item" },
    el("div", { class: "tete" }, pastille(x.niveau >= 3 ? "rouge" : "orange", x.niveau >= 3 ? "Niveau 3 — sponsor" : "Niveau 2 — projet"), el("span", { class: "titre" }, x.titre)),
    el("div", { class: "detail" }, x.detail)))));
  const groupes = new Map();
  for (const x of liste) { const k = x.partie_prenante || "Sans partie prenante"; if (!groupes.has(k)) groupes.set(k, []); groupes.get(k).push(x); }
  const fleche = x => (x.evolution === "hausse" ? ["↗", "vert"] : x.evolution === "baisse" ? ["↘", "rouge"] : x.evolution === "stable" ? ["→", "neutre"] : null);
  for (const [pp, lignes] of groupes) {
    const notees = lignes.filter(x => x.satisfaction != null);
    const moyenne = notees.length ? notees.reduce((s, x) => s + x.satisfaction, 0) / notees.length : null;
    v.append(el("h3", {}, pp, moyenne != null && el("span", { style: "font-weight:400;color:var(--doux)" }, ` · satisfaction moyenne ${(Math.round(moyenne * 10) / 10).toLocaleString("fr-FR")} / 5`)),
      tableau("attente", lignes.sort((a, b) => (a.priorite || 9) - (b.priorite || 9)), [
        ["Attente", l => [el("b", {}, l.libelle), l.categorie && el("div", {}, el("span", { class: "chip" }, l.categorie))], "long"],
        ["Priorité", l => (l.priorite ? "P" + l.priorite : "—")],
        ["Satisfaction", l => { const f = fleche(l); return [satisfaction(l.satisfaction), f && [" ", el("span", { class: "pastille evo " + f[1], title: `était ${l.satisfaction_precedente} / 5 (changé le ${dateFr(l.satisfaction_changee_le)})` }, f[0])]]; }],
        ["Position", l => pastille(POSITIONS[l.position] || "neutre", l.position || "—")],
        ["Notre réponse", l => [l.reponse || "", l.prochaine_action && el("div", { style: "color:var(--doux);font-size:13px" }, "→ " + l.prochaine_action)], "long"],
        ["Échéance", l => dateFr(l.echeance)],
        ["Revue", l => [dateFr(l.revue_le), l.revue_due ? [" ", pastille("orange", "À revoir")] : null]]], recharger));
  }
}];
