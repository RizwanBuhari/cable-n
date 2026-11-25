// A logo image with a looping sheen highlight, masked to the logo's own
// silhouette (see `.logo-shine` in base.css). Used on the home hero and
// the topbar so the effect is identical everywhere (carried over from
// Track-N).
//
// Props:
//   src        - image path (also used as the sheen mask)
//   alt        - alt text
//   shine      - 'light' (white glint, for dark logos on light backgrounds) or
//                'dark'  (soft dark sheen, for a white logo on a dark background)
//   className / imgClassName - extra classes for the wrapper / the <img>
//   fallback   - optional node rendered (hidden) after the logo; shown if the
//                image fails to load.
export default function LogoShine({
  src,
  alt,
  shine = 'light',
  className = '',
  imgClassName = '',
  fallback = null,
}) {
  return (
    <>
      <span
        className={`logo-shine logo-shine-${shine} ${className}`.trim()}
        style={{ '--logo-src': `url(${src})` }}
      >
        <img
          className={imgClassName}
          src={src}
          alt={alt}
          onError={(e) => {
            const wrap = e.currentTarget.parentElement
            wrap.style.display = 'none'
            if (wrap.nextElementSibling) {
              wrap.nextElementSibling.style.display = 'block'
            }
          }}
        />
      </span>
      {fallback}
    </>
  )
}
