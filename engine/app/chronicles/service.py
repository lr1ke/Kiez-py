async def archive(db, slug):
    return await db.rows(
        """SELECT id,neighborhood_id,diary_date,language,contribution_count,status,demo_dataset,
        CASE WHEN status='published' THEN title ELSE '' END AS title,
        CASE WHEN status='published' THEN body ELSE '' END AS body,
        CASE WHEN status='published' THEN source_ids ELSE '[]'::jsonb END AS source_ids
        FROM chronicles WHERE neighborhood_id=:id ORDER BY diary_date DESC""",
        id=slug,
    )


async def featured(db):
    return await db.rows("""WITH latest AS (
        SELECT DISTINCT ON(neighborhood_id) id,neighborhood_id,diary_date,title,body,language,
            source_ids,contribution_count,status,demo_dataset FROM chronicles WHERE status='published'
        ORDER BY neighborhood_id,diary_date DESC)
        SELECT jsonb_build_object('id',n.id,'name',n.name,'district',n.district,'aliases',n.aliases,
            'description',n.description,'color',n.color,'center',n.center,'geometry',n.geometry,
            'boundary_version',n.boundary_version) AS neighborhood,to_jsonb(c) AS story
        FROM latest c JOIN neighborhoods n ON n.id=c.neighborhood_id WHERE n.active
        ORDER BY n.display_order,n.id LIMIT 3""")
