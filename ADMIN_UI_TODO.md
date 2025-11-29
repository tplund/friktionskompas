# V3 Admin UI TODO

## Hvad skal ændres i Admin UI

Nu hvor database-laget er klar med hierarkisk struktur, skal admin UI'et opdateres til at matche.

---

## 1. **Bulk Upload Page** (`/admin/bulk-upload`)

### Nuværende
- Uploader organisations + departments som flat struktur
- Hårdkodet til at parse "Organisation" og "Afdeling" kolonner separat

### Skal ændres til
- Upload CSV med `//` separator i én kolonne
- Brug `csv_upload_hierarchical.py` funktioner:
  - `validate_csv_format()` før upload
  - `bulk_upload_from_csv()` til import
  - `generate_csv_template()` til download af skabelon

### UI ændringer
```python
# admin_app.py: /admin/bulk-upload route
from csv_upload_hierarchical import (
    validate_csv_format, 
    bulk_upload_from_csv,
    generate_csv_template
)

@app.route('/admin/bulk-upload', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'POST':
        file = request.files['file']
        content = file.stream.read().decode('UTF8')
        
        # Valider først
        validation = validate_csv_format(content)
        if not validation['valid']:
            flash(f"❌ Fejl i CSV: {validation['errors']}", 'error')
            return redirect(request.url)
        
        # Upload
        stats = bulk_upload_from_csv(content)
        flash(f"✅ {stats['units_created']} units oprettet!", 'success')
        
        return redirect(url_for('admin_home'))
    
    # GET: Vis upload form med preview
    return render_template('admin/bulk_upload.html')

@app.route('/admin/csv-template')
def download_csv_template():
    """Download CSV skabelon"""
    template = generate_csv_template()
    return Response(
        template,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=skabelon.csv'}
    )
```

---

## 2. **Admin Home** (`/admin`)

### Nuværende
- Lister organisations flat

### Skal ændres til
- Vis top-level units (hvor `parent_id IS NULL`)
- Klikbare for at se subtræ
- Vise antal descendants

### SQL Query
```python
@app.route('/admin')
def admin_home():
    with get_db() as conn:
        # Top-level units
        top_units = conn.execute("""
            SELECT 
                ou.*,
                COUNT(DISTINCT children.id) as descendant_count,
                COUNT(DISTINCT leaf.id) as leaf_count
            FROM organizational_units ou
            LEFT JOIN organizational_units children ON children.parent_id = ou.id
            LEFT JOIN (
                SELECT ou2.* FROM organizational_units ou2
                LEFT JOIN organizational_units c ON ou2.id = c.parent_id
                WHERE c.id IS NULL
            ) leaf ON leaf.full_path LIKE ou.full_path || '%'
            WHERE ou.parent_id IS NULL
            GROUP BY ou.id
            ORDER BY ou.name
        """).fetchall()
    
    return render_template('admin/home.html', units=[dict(u) for u in top_units])
```

---

## 3. **Unit Detail View** (`/admin/unit/<unit_id>`)

### Nyt route
Erstat `/admin/org/<org_id>` og `/admin/dept/<dept_id>` med én generic unit view

```python
from db_hierarchical import (
    get_unit_children, 
    get_unit_path,
    get_leaf_units
)

@app.route('/admin/unit/<unit_id>')
def view_unit(unit_id):
    with get_db() as conn:
        # Hent unit
        unit = conn.execute(
            "SELECT * FROM organizational_units WHERE id = ?",
            (unit_id,)
        ).fetchone()
        
        if not unit:
            flash("❌ Unit ikke fundet", 'error')
            return redirect(url_for('admin_home'))
    
    # Breadcrumbs
    breadcrumbs = get_unit_path(unit_id)
    
    # Direct children
    children = get_unit_children(unit_id, recursive=False)
    
    # Leaf units under dette (for campaigns)
    leaf_units = get_leaf_units(unit_id)
    
    # Campaigns rettet mod denne unit
    with get_db() as conn:
        campaigns = conn.execute("""
            SELECT * FROM campaigns 
            WHERE target_unit_id = ?
            ORDER BY created_at DESC
        """, (unit_id,)).fetchall()
    
    return render_template('admin/view_unit.html',
        unit=dict(unit),
        breadcrumbs=breadcrumbs,
        children=children,
        leaf_units=leaf_units,
        campaigns=[dict(c) for c in campaigns]
    )
```

---

## 4. **Create Unit** (`/admin/unit/new`)

### To modes

**Mode 1: Simpel (anbefalet for de fleste)**
```python
@app.route('/admin/unit/new', methods=['GET', 'POST'])
def new_unit():
    if request.method == 'POST':
        path = request.form['path']  # "TechCorp//IT//Development"
        leader_name = request.form.get('leader_name')
        leader_email = request.form.get('leader_email')
        employee_count = int(request.form.get('employee_count', 0))
        
        unit_id = create_unit_from_path(
            path=path,
            leader_name=leader_name,
            leader_email=leader_email,
            employee_count=employee_count
        )
        
        flash(f"✅ Unit '{path}' oprettet!", 'success')
        return redirect(url_for('view_unit', unit_id=unit_id))
    
    return render_template('admin/new_unit.html')
```

**Mode 2: Avanceret (vælg parent fra dropdown)**
- Vælg parent unit fra dropdown
- Angiv kun navn (ikke full path)
- Bedre for at tilføje én unit ad gangen

---

## 5. **Campaign Creation** (`/admin/campaign/new`)

### Nuværende
- Vælg organisation
- Vælg flere departments med checkboxes

### Skal ændres til
- Vælg én target unit
- Vis preview af hvilke leaf units der rammes
- Vis total antal tokens der genereres

```python
@app.route('/admin/campaign/new', methods=['GET', 'POST'])
def new_campaign():
    if request.method == 'POST':
        target_unit_id = request.form['target_unit_id']
        name = request.form['name']
        period = request.form['period']
        
        # Opret campaign
        campaign_id = create_campaign(
            target_unit_id=target_unit_id,
            name=name,
            period=period
        )
        
        # Generer tokens
        tokens_by_unit = generate_tokens_for_campaign(campaign_id)
        total_tokens = sum(len(t) for t in tokens_by_unit.values())
        
        flash(f"✅ Kampagne oprettet! {total_tokens} tokens genereret", 'success')
        return redirect(url_for('view_campaign', campaign_id=campaign_id))
    
    # GET: Vis form
    # Load units som træ for dropdown
    with get_db() as conn:
        units = conn.execute("""
            SELECT id, name, full_path, level 
            FROM organizational_units
            ORDER BY full_path
        """).fetchall()
    
    return render_template('admin/new_campaign.html', 
        units=[dict(u) for u in units]
    )
```

---

## 6. **Campaign View** (`/admin/campaign/<campaign_id>`)

### Ændringer
- Vis target unit med breadcrumbs
- Vis hvilke leaf units der fik tokens
- Aggregeret data kan vises på flere niveauer

```python
from db_hierarchical import get_unit_stats, get_campaign_overview

@app.route('/admin/campaign/<campaign_id>')
def view_campaign(campaign_id):
    with get_db() as conn:
        campaign = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?",
            (campaign_id,)
        ).fetchone()
        
        if not campaign:
            flash("❌ Kampagne ikke fundet", 'error')
            return redirect(url_for('admin_home'))
    
    # Target unit info
    target_unit_id = campaign['target_unit_id']
    breadcrumbs = get_unit_path(target_unit_id)
    
    # Overview af alle leaf units
    overview = get_campaign_overview(campaign_id)
    
    # Aggregeret stats for target unit (inkl. children)
    aggregate_stats = get_unit_stats(
        unit_id=target_unit_id,
        campaign_id=campaign_id,
        include_children=True
    )
    
    return render_template('admin/view_campaign.html',
        campaign=dict(campaign),
        target_breadcrumbs=breadcrumbs,
        overview=overview,
        aggregate_stats=aggregate_stats
    )
```

---

## 7. **Templates der skal opdateres**

### Templates til unit visning
- `templates/admin/home.html` - vis top-level units
- `templates/admin/view_unit.html` - generic unit view (erstatter view_org.html og view_dept.html)
- `templates/admin/new_unit.html` - opret ny unit

### Templates til campaigns
- `templates/admin/new_campaign.html` - vælg target unit i stedet for multiple depts
- `templates/admin/view_campaign.html` - vis target unit + affected leaf units

### Bulk upload
- `templates/admin/bulk_upload.html` - tilføj CSV preview og validation

---

## 8. **Nice-to-have UI features**

### Træ-visualisering
```html
<!-- Vis hierarki som træ med indentation -->
<div class="org-tree">
  <div class="unit level-0">
    <strong>TechCorp</strong>
    <div class="unit level-1">
      IT Afdeling
      <div class="unit level-2">• Development (15 medarbejdere)</div>
      <div class="unit level-2">• Support (8 medarbejdere)</div>
    </div>
  </div>
</div>
```

### Drag-and-drop reorganisering
- Kunne flytte units til andre parents
- Opdater `parent_id` og genberegn `full_path`

### Bulk edit
- Opdater sick_leave for mange units ad gangen
- Opdater leader info

---

## Prioriteret rækkefølge

1. ✅ **Database layer** (DONE - db_hierarchical.py)
2. ✅ **CSV upload** (DONE - csv_upload_hierarchical.py)
3. 🔄 **Admin home** - vis top-level units
4. 🔄 **View unit** - generic unit detail view
5. 🔄 **Create unit** - simpel path-based creation
6. 🔄 **Campaign creation** - vælg target unit
7. 🔄 **Campaign view** - vis affected units

---

## Claude Code tid! 🚀

Nu er database-laget klar. Næste skridt er at opdatere admin_app.py og templates.

Dette er perfekt til Claude Code fordi:
- Mange filer skal rettes samtidigt
- Konsistent refactoring på tværs af routes
- Template opdateringer der hænger sammen med backend

Klar til at gå i gang? 💪
