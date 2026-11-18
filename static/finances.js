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
    el("button", { class: "principal", onclick: () => dialogueCatalogue(mode) }, "Catalogue de blocs"),
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
      tuile("TJM moyen", euros(c.tjm_moyen), m.sans_valorisation ? `${m.sans_valorisation} ligne(s) sans TJM` : "profils de la vue Budget"),
      tuile("Incertitude", m.incertitude.etendue == null ? "—" : "± " + pourcent(m.incertitude.etendue),
        [`${pourcent(m.incertitude.part_sans_information)} de la charge sans information`,
          m.incertitude.couverture_contingence != null ? el("div", {}, "contingence : ", pastille(m.incertitude.couverture_contingence >= 0.5 ? "vert" : "orange",
            pourcent(m.incertitude.couverture_contingence) + " du risque haut")) : null,
          m.incertitude.sans_profil ? el("div", {}, pastille("orange", `${m.incertitude.sans_profil} ligne(s) sans profil`)) : null])));
    const cols = mode === "macro"
      ? [["Lot", l => pastilleLot(l.lot)], ["Élément", l => [el("b", {}, l.libelle), l.hypothese && el("div", { style: "color:var(--doux);font-size:13px" }, l.hypothese)], "long"],
        ["Taille", l => l.taille || (l.jours_probable != null ? "saisie" : pastille("orange", "à dimensionner"))], ["Confiance", l => l.confiance || "moyenne"],
        ["Bas", l => jours(l.bas), "num"], ["Retenu", l => el("b", {}, jours(l.retenu)), "num"], ["Haut", l => jours(l.haut), "num"], ["Montant", l => euros(l.montant), "num"]]
      : [["Lot", l => pastilleLot(l.lot)], ["Élément", l => [el("b", {}, l.libelle), l.hypothese && el("div", { style: "color:var(--doux);font-size:13px" }, l.hypothese)], "long"],
        ["Profil", l => l.profil || pastille("orange", "à affecter")], ["Bas", l => jours(l.bas), "num"], ["Probable", l => jours(l.jours_probable), "num"],
        ["Haut", l => jours(l.haut), "num"], ["PERT", l => el("b", {}, jours(l.retenu)), "num"], ["Montant", l => euros(l.montant), "num"]];
    v.append(el("h3", {}, "Éléments chiffrés"), tableau("estimation", m.lignes, cols, recharger));
  }

  const hyps = (await api("GET", "hypothese")).filter(h => ["chiffrage", "périmètre", "budget"].includes(h.categorie));
  v.append(section("Hypothèses du chiffrage", "hypothese", hyps, colonnesHypotheses, recharger));
  if (hyps.some(h => h.statut === "invalidée"))
    v.append(el("div", { class: "bandeau", style: "margin-top:8px" }, "Une hypothèse du chiffrage est invalidée : le chiffrage est à revoir, ou à défendre par une demande de changement."));
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
  const [b, factures] = await Promise.all([api("GET", "budget"), api("GET", "facture")]);
  v.append(titreVue("Budget",
    "Vais-je atterrir dans l'enveloppe ? Vendu, consommé, reste à faire et atterrissage, valorisés aux TJM des profils, et l'échéancier de facturation. Mettez à jour le reste à faire de chaque profil à chaque point budgétaire.",
    el("button", { onclick: () => dialogueBudgetVendu(b.vendu) }, "Budget vendu"),
    el("button", { onclick: () => afficher("budget_saisie") }, "Saisir temps et dépenses")));
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
  const auj = new Date().toISOString().slice(0, 10);
  v.append(section("Échéancier de facturation", "facture", factures, [
    ["Échéance", l => l.libelle, "long"], ["Jalon", l => l.jalon || "—"], ["Date prévue", l => dateFr(l.date_prevue)],
    ["Montant", l => euros(l.montant), "num"],
    ["Statut", l => [pastille(l.statut === "payée" ? "vert" : l.statut === "facturée" ? "neutre" : "orange", l.statut || "à facturer"),
      (l.statut || "à facturer") === "à facturer" && l.date_prevue && l.date_prevue < auj ? [" ", pastille("rouge", "En retard")] : null]]], recharger));
}];

// Saisie du budget : temps consommés et dépenses (l'analyse est dans la vue Budget).
VUES.budget_saisie = ["Saisie du budget", "Saisie", async v => {
  const [consommations, depenses] = await Promise.all([api("GET", "consommation"), api("GET", "depense")]);
  v.append(titreVue("Saisie du budget",
    "Les temps passés par mois et par profil, et les dépenses hors temps passé. Ils alimentent le consommé et l'atterrissage de la vue Budget.",
    el("button", { onclick: () => afficher("budget") }, "Voir le budget")));
  v.append(section("Temps consommés", "consommation", [...consommations].reverse(), [
    ["Mois", l => l.mois || "—"], ["Profil", l => l.profil || "—"], ["Jours", l => jours(l.jours), "num"],
    ["Montant", l => euros((l.jours || 0) * (ref.profils.find(p => p.nom === l.profil)?.tjm || 0)), "num"], ["Commentaire", l => l.commentaire || "", "long"]], recharger));
  v.append(section("Dépenses hors temps passé", "depense", depenses, [
    ["Dépense", l => l.libelle, "long"], ["Catégorie", l => l.categorie || "—"], ["Date", l => dateFr(l.date)],
    ["Montant", l => euros(l.montant), "num"], ["Statut", l => pastille(l.statut === "payée" ? "vert" : l.statut === "engagée" ? "neutre" : "orange", l.statut || "prévue")]], recharger));
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

// ---------- Catalogue de blocs de chiffrage ----------
const NIV_CLASSE = { rapide: "vert", moyen: "orange", long: "rouge" };
const sansAccent = t => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const lignesRoles = roles => Object.entries(roles || {}).map(([r, j]) => `${r} : ${String(j).replace(".", ",")}`).join("\n");
function lireRoles(texte) {
  const out = {};
  for (const ligne of texte.split("\n").map(l => l.trim()).filter(Boolean)) {
    const m = /^(.+?)\s*[:=]\s*([\d.,]+)\s*j?$/.exec(ligne);
    if (!m) throw new Error(`Ligne illisible : « ${ligne} ». Format attendu : Rôle : jours`);
    out[m[1].trim()] = Number(m[2].replace(",", "."));
  }
  return out;
}

async function dialogueCatalogue(mode) {
  const d = $("#dialogue"), cat = await api("GET", "catalogue");
  d.classList.add("large");
  if (!d.dataset.nettoyage) {
    d.dataset.nettoyage = "1";
    d.addEventListener("close", () => { if (d.classList.contains("large")) { d.classList.remove("large"); recharger(); } });
  }
  const etatCat = dialogueCatalogue.etat || (dialogueCatalogue.etat = { recherche: "", famille: "", lot: "", quantite: 1 });
  let ajoutes = 0;
  const compteur = el("span", { class: "aide", style: "margin:0" });
  const familles = [...new Set(cat.blocs.map(b => b.famille))];
  const liste = el("div", { style: "display:grid;gap:8px;max-height:56vh;overflow-y:auto;padding-right:4px" });
  const ajouter = async (b, n, bouton) => {
    await pendant(bouton, "…", async () => {
      const crees = await api("POST", "catalogue/appliquer", { bloc: b.id, niveau: n, mode, lot: etatCat.lot, quantite: Number(etatCat.quantite) || 1 });
      ajoutes += crees.length;
      compteur.textContent = `${ajoutes} ligne(s) ajoutée(s) au chiffrage ${MODES[mode][0].toLowerCase()}.`;
      dire(`« ${b.nom} » ajouté (${cat.niveaux[n].libelle.toLowerCase()}).`);
    });
  };
  const dessiner = () => {
    const r = sansAccent(etatCat.recherche), q = Number(etatCat.quantite) || 1;
    const blocs = cat.blocs.filter(b => (!etatCat.famille || b.famille === etatCat.famille)
      && (!r || sansAccent(`${b.id} ${b.nom} ${b.famille} ${b.description}`).includes(r)));
    const parFamille = familles.map(f => [f, blocs.filter(b => b.famille === f)]).filter(([, l]) => l.length);
    liste.replaceChildren(parFamille.length ? parFamille.map(([f, l]) => [
      el("h4", { style: "margin:8px 0 0;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--doux)" }, f),
      l.map(b => el("div", { class: "item" },
        el("div", { class: "tete" }, el("span", { class: "titre" }, b.nom),
          el("span", { style: "color:var(--doux);font-size:13px" }, b.unite),
          b.origine === "personnalisé" && pastille("neutre", "personnalisé"),
          el("button", { type: "button", class: "lien", style: "margin-left:auto;font-size:13px", onclick: () => editeurBloc(b, cat, mode) }, "Personnaliser")),
        el("div", { class: "detail", style: "font-size:13.5px" }, b.description),
        el("div", { class: "niveaux-bloc" }, Object.entries(cat.niveaux).map(([n, def]) => el("div", { class: "niveau-bloc" },
          el("button", { type: "button", title: "Ajouter ce niveau au chiffrage", onclick: e => ajouter(b, n, e.currentTarget) },
            pastille(NIV_CLASSE[n], def.duree), ` ${def.libelle} · ${jours(b.totaux[n] * q)}`),
          b.criteres[n] && el("p", {}, b.criteres[n]),
          el("small", {}, Object.entries(b.niveaux[n]).map(([r, j]) => `${r} ${jours(j * q)}`).join(" · ")))))))])
      : el("div", { class: "vide" }, "Aucun bloc ne correspond."));
  };
  const recherche = el("input", { type: "search", placeholder: "Rechercher (données, API, recette…)", "aria-label": "Rechercher un bloc", oninput: e => { etatCat.recherche = e.target.value; dessiner(); } });
  recherche.value = etatCat.recherche;
  const famille = el("select", { "aria-label": "Famille", onchange: e => { etatCat.famille = e.target.value; dessiner(); } },
    el("option", { value: "" }, "Toutes les familles"), familles.map(f => el("option", { value: f, selected: f === etatCat.famille }, f)));
  const lot = el("select", { onchange: e => { etatCat.lot = e.target.value; } },
    el("option", { value: "" }, "Sans lot"), nomsLots().map(n => el("option", { value: n, selected: n === etatCat.lot }, n)));
  const quantite = el("input", { type: "number", min: "0.5", step: "0.5", oninput: e => { etatCat.quantite = e.target.value; dessiner(); } });
  quantite.value = etatCat.quantite;
  d.replaceChildren(el("form", { method: "dialog", onsubmit: e => { e.preventDefault(); d.close(); } },
    el("h3", {}, `Catalogue de blocs — chiffrage ${MODES[mode][0].toLowerCase()}`),
    el("p", { class: "aide", style: "margin:0" },
      "Chaque bloc a trois niveaux : simple et clair (rapide), compliqué mais chemin clair (moyen), aucune information (long). "
      + (mode === "detaille" ? "En détaillé, une ligne par rôle, rapprochée de vos profils par nom puis par métier." : "En macro, une ligne par bloc avec la fourchette du niveau.")
      + " Les charges sont un point de départ : personnalisez-les pour votre contexte."),
    el("div", { class: "champs", style: "grid-template-columns:2fr 1.4fr 1fr .8fr;align-items:end" }, recherche, famille,
      el("label", {}, "Lot", lot), el("label", {}, "Quantité", quantite)),
    liste,
    el("div", { class: "barre" }, compteur, el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => editeurBloc(null, cat, mode) }, "Nouveau bloc"),
      el("button", { class: "principal" }, "Terminer"))));
  dessiner();
  if (!d.open) d.showModal();
}

function editeurBloc(b, cat, mode) {
  const d = $("#dialogue");
  const nom = el("input", { required: true }), famille = el("input"), unite = el("input"), description = el("textarea");
  nom.value = b?.nom || ""; famille.value = b?.famille || "Mes blocs"; unite.value = b?.unite || ""; description.value = b?.description || "";
  const zones = Object.fromEntries(Object.keys(cat.niveaux).map(n => {
    const t = el("textarea", { style: "min-height:110px;font-family:Consolas,monospace;font-size:13px" });
    t.value = lignesRoles(b?.niveaux[n]); return [n, t];
  }));
  const quand = Object.fromEntries(Object.keys(cat.niveaux).map(n => {
    const t = el("textarea", { style: "min-height:120px;font-size:13.5px", placeholder: "Dans quelle situation choisir ce niveau, ce que couvre la charge" });
    t.value = b?.criteres?.[n] || ""; return [n, t];
  }));
  const retour = () => dialogueCatalogue(mode);
  d.replaceChildren(el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    try {
      const corps = { nom: nom.value, famille: famille.value, unite: unite.value, description: description.value,
        niveaux: Object.fromEntries(Object.entries(zones).map(([n, t]) => [n, lireRoles(t.value)])),
        criteres: Object.fromEntries(Object.entries(quand).map(([n, t]) => [n, t.value])) };
      await api(b ? "PUT" : "POST", b ? `catalogue/${b.id}` : "catalogue", corps);
      dire("Bloc enregistré dans le catalogue (commun à toutes les missions)."); await retour();
    } catch (err) { dire(err.message, true); }
  } },
    el("h3", {}, b ? "Personnaliser : " + b.nom : "Nouveau bloc"),
    el("div", { class: "champs" }, el("label", { class: "large" }, "Nom", nom), el("label", {}, "Famille", famille),
      el("label", {}, "Unité (par source, par écran…)", unite), el("label", { class: "large" }, "Ce que couvre le bloc", description)),
    el("p", { class: "aide", style: "margin:0" }, `Une ligne par rôle : « Rôle : jours ». Rôles types : ${cat.roles.join(", ")} (ou le nom d'un de vos profils).`),
    el("div", { class: "champs", style: "grid-template-columns:repeat(3,1fr)" }, Object.entries(cat.niveaux).map(([n, def]) =>
      el("label", {}, [pastille(NIV_CLASSE[n], def.duree), " ", def.libelle], el("span", {}, "Quand le choisir"), quand[n],
        el("span", {}, "Jours par rôle"), zones[n]))),
    el("div", { class: "barre" },
      b?.origine === "personnalisé" && el("button", { type: "button", class: "danger", onclick: async () => {
        if (!confirm("Retirer la personnalisation de ce bloc ? Un bloc du catalogue d'origine retrouve ses valeurs ; un bloc créé par vous disparaît.")) return;
        try { await api("DELETE", `catalogue/${b.id}`); dire("Personnalisation retirée."); await retour(); } catch (err) { dire(err.message, true); }
      } }, "Retirer la personnalisation"),
      el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: retour }, "Retour"),
      el("button", { class: "principal" }, "Enregistrer"))));
  if (!d.open) d.showModal();
}
