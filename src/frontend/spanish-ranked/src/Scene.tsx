import { useEffect, useState, type CSSProperties } from 'react'

type SceneDef = {
  id: string
  place: string
  title: string
  /** Photographer / licence line shown under the caption once a photo exists. */
  credit?: string
  /** Gradient tints used until (or if) the photo is missing. */
  s1: string
  s2: string
  s3: string
}

// Photos live at public/scenes/<id>.webp. Until a file exists the tinted gradient shows instead.
const SCENES: SceneDef[] = [
  { id: 'granada', place: 'Granada', title: 'The Alhambra at dusk', s1: '#2b2f3a', s2: '#8a6a4a', s3: '#c28a5a' },
  { id: 'tonanes', place: 'Cantabria', title: 'Cliffs at Toñanes on the coast path', credit: 'Photo: Hotelpalacion, CC BY-SA 4.0, Wikimedia Commons', s1: '#1f2a33', s2: '#5d6f78', s3: '#c9b48f' },
  { id: 'salamanca', place: 'Salamanca', title: 'The old university', s1: '#2a1f18', s2: '#6b4a2f', s3: '#b88a4f' },
  { id: 'cantabria', place: 'Cantabria', title: 'Estuary and green hills on the coast', credit: 'Photo: Pexels, free to use', s1: '#18262a', s2: '#3f6a5c', s3: '#9fb59a' },
  { id: 'sevilla', place: 'Sevilla', title: 'The Torre del Oro at dusk', credit: 'Photo: Benjamin Smith, CC BY-SA 4.0, Wikimedia Commons', s1: '#2a2218', s2: '#7c6a3a', s3: '#d0a95c' },
]

/** One scene per calendar day, the same all day. */
function todaysScene(): SceneDef {
  const now = new Date()
  const day = Math.floor(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / 86_400_000)
  return SCENES[day % SCENES.length]
}

export default function Scene() {
  const [scene] = useState(todaysScene)
  const src = `/scenes/${scene.id}.webp`
  const [hasPhoto, setHasPhoto] = useState(false)

  // Preload so a missing file falls back silently and the caption only claims a photo that is really there.
  useEffect(() => {
    const img = new Image()
    img.onload = () => setHasPhoto(true)
    img.src = src
    return () => {
      img.onload = null
    }
  }, [src])

  const style = {
    '--s1': scene.s1,
    '--s2': scene.s2,
    '--s3': scene.s3,
    ...(hasPhoto ? { '--photo': `url(${src})` } : {}),
  } as CSSProperties

  if (!hasPhoto) return <div className="scene" style={style} aria-hidden="true" />

  return (
    <figure className="scene" style={style} role="img" aria-label={`${scene.place}: ${scene.title}`}>
      <figcaption className="scene-cap">
        <span className="cap-place">{scene.place}</span> {scene.title}
        {scene.credit && <span className="cap-credit">{scene.credit}</span>}
      </figcaption>
    </figure>
  )
}
