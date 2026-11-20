import { useEffect, useRef, useState } from 'react';
import * as C from 'cesium';

const amber = C.Color.fromCssColorString('#F2B84B');
const green = C.Color.fromCssColorString('#BDE8A4');
const red = C.Color.fromCssColorString('#F0705A');
const center = [-120.108177, 36.341988];
const origin = [-120.108177, 36.33615];
const color = hex => C.Color.fromCssColorString(hex);

function ring(geometry) {
  if (geometry.type === 'MultiPolygon') return geometry.coordinates[0][0];
  return geometry.coordinates[0];
}

function outline(viewer, id, geometry, material, width = 2, height = 4) {
  const rings = geometry.type === 'MultiPolygon' ? geometry.coordinates.map(p => p[0]) : [geometry.coordinates[0]];
  rings.forEach((coords, i) => viewer.entities.add({
    id: `${id}-${i}`,
    polyline: { positions: C.Cartesian3.fromDegreesArrayHeights(coords.flatMap(p => [p[0], p[1], height])),
      material, width, arcType: C.ArcType.GEODESIC },
  }));
}

function frameGround(viewer, points, duration) {
  const rectangle = C.Rectangle.fromCartesianArray(C.Cartesian3.fromDegreesArray(points.flat()));
  const lon = C.Math.toDegrees((rectangle.west + rectangle.east) / 2);
  const lat = C.Math.toDegrees((rectangle.south + rectangle.north) / 2);
  const width = viewer.scene.canvas.clientWidth, height = viewer.scene.canvas.clientHeight;
  const rail = document.querySelector('.left-rail')?.getBoundingClientRect();
  const consoleRect = document.querySelector('.right-console')?.getBoundingClientRect();
  const mobile = width <= 760;
  const left = mobile ? 15 : (rail?.right || 0) + 24;
  const right = mobile ? width - 15 : (consoleRect?.left || width) - 24;
  const top = mobile ? 130 : 170;
  const bottom = mobile ? Math.max(300, height * .43) : height - 170;
  const availableWidth = Math.max(200, right - left);
  const availableHeight = Math.max(150, bottom - top);
  const spanX = Math.max(220, rectangle.width * 6378137 * Math.cos(lat * Math.PI/180));
  const spanY = Math.max(220, rectangle.height * 6378137);
  const fov = Math.tan(viewer.camera.frustum.fovy / 2);
  const altitude = Math.max(650, spanX * width / availableWidth / (2*fov*(width/height)), spanY * height / availableHeight / (2*fov)) * 1.2;
  const mpp = 2 * altitude * fov / height;
  const targetLon = lon + (width/2-(left+right)/2) * mpp / (111320*Math.cos(lat*Math.PI/180));
  const targetLat = lat - (height/2-(top+bottom)/2) * mpp / 111320;
  const options = { destination: C.Cartesian3.fromDegrees(targetLon, targetLat, altitude),
    orientation: { heading: 0, pitch: -Math.PI/2, roll: 0 } };
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) viewer.camera.setView(options);
  else viewer.camera.flyTo({ ...options, duration });
}

export default function Globe({ data, selected, onSelect, mission, progress, flying, ndviVisible, scenario, overviewKey, application }) {
  const element = useRef(null);
  const viewerRef = useRef(null);
  const selectRef = useRef(onSelect);
  const imageryRef = useRef({});
  const missionRef = useRef(null);
  const flightRef = useRef(0);
  const visibilityRef = useRef({ selected, ndviVisible, cloud: scenario.cloud });
  const [error, setError] = useState(null);
  const [aerialStatus, setAerialStatus] = useState('Esri World Imagery');
  selectRef.current = onSelect;
  visibilityRef.current = { selected, ndviVisible, cloud: scenario.cloud };

  useEffect(() => {
    let viewer;
    let handler;
    imageryRef.current = {};
    try {
      C.Ion.defaultAccessToken = '';
      viewer = new C.Viewer(element.current, {
        baseLayer: false, terrainProvider: new C.EllipsoidTerrainProvider(),
        animation: false, timeline: false, baseLayerPicker: false, geocoder: false,
        homeButton: false, sceneModePicker: false, navigationHelpButton: false,
        fullscreenButton: false, infoBox: false, selectionIndicator: false,
        requestRenderMode: true, maximumRenderTimeChange: Infinity,
        contextOptions: { webgl: { alpha: false } },
      });
      viewerRef.current = viewer;
      viewer.scene.backgroundColor = color('#0E2A1B');
      viewer.scene.globe.baseColor = color('#0E2A1B');
      viewer.scene.globe.showGroundAtmosphere = true;
      viewer.scene.globe.enableLighting = false;
      viewer.scene.fog.enabled = false;
      viewer.scene.skyBox.show = true;
      viewer.scene.skyAtmosphere.hueShift = -.06;
      viewer.scene.skyAtmosphere.brightnessShift = -.35;
      viewer.scene.sun.show = false;
      viewer.scene.moon.show = false;
      const world = new C.UrlTemplateImageryProvider({
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        credit: 'Esri, Maxar, Earthstar Geographics, and the GIS User Community', maximumLevel: 19,
      });
      const base = viewer.imageryLayers.addImageryProvider(world);
      base.brightness = .37;
      base.saturation = .25;
      imageryRef.current.base = base;
      // Public NASA night lights make California legible from orbit, without an Ion key.
      const night = new C.WebMapTileServiceImageryProvider({
        url: 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/wmts.cgi',
        layer: 'VIIRS_CityLights_2012', style: 'default', format: 'image/jpeg',
        tileMatrixSetID: 'GoogleMapsCompatible_Level8', maximumLevel: 8,
        credit: 'NASA GIBS / VIIRS city lights, 2012 (basemap only)',
      });
      const nightLayer = viewer.imageryLayers.addImageryProvider(night);
      nightLayer.alpha = .7;
      imageryRef.current.night = nightLayer;
      viewer.camera.setView({ destination: C.Cartesian3.fromDegrees(-117, 31, 11_000_000),
        orientation: { heading: C.Math.toRadians(-10), pitch: C.Math.toRadians(-87), roll: 0 } });
      viewer.entities.add({ id: 'site-reticle', position: C.Cartesian3.fromDegrees(...center, 500),
        point: { pixelSize: 11, color: amber, outlineColor: amber.withAlpha(.25), outlineWidth: 14,
          disableDepthTestDistance: Number.POSITIVE_INFINITY },
        label: { text: 'FIVE POINTS / CA', font: '12px Geist Mono', fillColor: amber,
          pixelOffset: new C.Cartesian2(20, -3), horizontalOrigin: C.HorizontalOrigin.LEFT,
          showBackground: true, backgroundColor: color('#0E2A1B').withAlpha(.7),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new C.DistanceDisplayCondition(18000, 30_000_000) } });
      handler = new C.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction(movement => {
        const pick = viewer.scene.pick(movement.position);
        const fieldId = pick?.id?.properties?.fieldId?.getValue();
        if (fieldId) selectRef.current(fieldId);
      }, C.ScreenSpaceEventType.LEFT_CLICK);
      viewer.scene.renderError.addEventListener((_, err) => setError(`Globe rendering stopped: ${err.message}. Use the field queue to continue.`));
    } catch (err) {
      setError(`WebGL is unavailable: ${err.message}. The field queue and simulator remain available.`);
    }
    return () => { flightRef.current++; handler?.destroy(); if (viewer && !viewer.isDestroyed()) viewer.destroy(); viewerRef.current = null; imageryRef.current = {}; };
  }, []);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !data) return;
    const reticle = viewer.entities.getById('site-reticle');
    if (reticle && data.fields.length) reticle.properties = new C.PropertyBag({ fieldId: data.fields[0].id });
    const remove = viewer.entities.values.filter(e => e.id.startsWith('pin-') || e.id.startsWith('boundary-'));
    remove.forEach(e => viewer.entities.remove(e));
    data.fields.filter(f => f.packet.score > 0 || f.packet.action === 'defer_observation').slice(0, 12).forEach(field => {
      const hollow = field.packet.action === 'defer_observation' || scenario.cloud || scenario.stale;
      viewer.entities.add({ id: `pin-${field.id}`, properties: { fieldId: field.id },
        position: C.Cartesian3.fromDegrees(...field.center, 6),
        point: { pixelSize: field.id === selected?.id ? 12 : 8,
          color: hollow ? color('#1B4D30') : amber, outlineColor: amber, outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new C.DistanceDisplayCondition(0, 600_000) },
        label: { text: String(field.rank).padStart(2, '0'), font: '12px Geist Mono',
          fillColor: amber, showBackground: true, backgroundColor: color('#0E2A1B').withAlpha(.8),
          pixelOffset: new C.Cartesian2(14, -13), disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new C.DistanceDisplayCondition(0, 12000) } });
      outline(viewer, `boundary-${field.id}`, field.geometry, amber.withAlpha(field.id === selected?.id ? .95 : .25), field.id === selected?.id ? 2 : 1);
    });
    viewer.scene.requestRender();
  }, [data, selected?.id, scenario.cloud, scenario.stale]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !selected || !data) return;
    const token = ++flightRef.current;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const points = ring(selected.geometry);
    frameGround(viewer, points, 2.5);
    const begin = performance.now();
    const fade = () => {
      if (token !== flightRef.current || viewer.isDestroyed()) return;
      const t = reduced ? 1 : Math.min(1, (performance.now() - begin) / 2200);
      imageryRef.current.base.brightness = .37 + t * .63;
      imageryRef.current.base.saturation = .25 + t * .75;
      if (imageryRef.current.night) imageryRef.current.night.alpha = .7 * (1 - t);
      if (imageryRef.current.aerial) imageryRef.current.aerial.alpha = t;
      viewer.scene.requestRender();
      if (t < 1) requestAnimationFrame(fade);
    };
    fade();
    viewer.entities.removeById('depot');
    viewer.entities.add({ id: 'depot', position: C.Cartesian3.fromDegrees(...origin, 8),
      point: { pixelSize: 10, color: green, outlineWidth: 3, outlineColor: color('#0E2A1B'), disableDepthTestDistance: Infinity },
      label: { text: 'DEPOT / AUTHORED', font: '12px Geist Mono', fillColor: green,
        pixelOffset: new C.Cartesian2(16, 0), horizontalOrigin: C.HorizontalOrigin.LEFT,
        disableDepthTestDistance: Infinity, showBackground: true, backgroundColor: color('#0E2A1B').withAlpha(.8) } });
    return () => { flightRef.current++; };
  }, [selected?.id, data?.snapshot_id]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !data) return;
    let cancelled = false;
    if (imageryRef.current.ndvi) viewer.imageryLayers.remove(imageryRef.current.ndvi, true);
    imageryRef.current.ndvi = null;
    const measurement = selected && data.ndvi_images?.[selected.id] || data.ndvi_url;
    const measurementUrl = measurement.startsWith('data:') ? measurement : measurement + (selected ? `&field_id=${selected.id}` : '');
    C.SingleTileImageryProvider.fromUrl(measurementUrl, { rectangle: C.Rectangle.fromDegrees(...data.ndvi_bounds) })
      .then(provider => {
        if (cancelled || viewer.isDestroyed()) return;
        const layer = viewer.imageryLayers.addImageryProvider(provider);
        layer.minificationFilter = C.TextureMinificationFilter.NEAREST;
        layer.magnificationFilter = C.TextureMagnificationFilter.NEAREST;
        layer.alpha = visibilityRef.current.cloud ? .15 : .63;
        layer.show = !!visibilityRef.current.selected && visibilityRef.current.ndviVisible;
        imageryRef.current.ndvi = layer;
        viewer.scene.requestRender();
      }).catch(err => setError(`Measurement overlay unavailable: ${err.message}`));
    return () => { cancelled = true; };
  }, [data?.snapshot_id, selected?.id]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !data) return;
    if (data.aerial.mode === 'NAIP') {
      const provider = new C.UrlTemplateImageryProvider({ url: data.aerial.url,
        rectangle: C.Rectangle.fromDegrees(...data.site.bbox), maximumLevel: 20,
        minimumLevel: 13,
        credit: `USDA NAIP / Planetary Computer ${data.aerial.date?.slice(0, 10) || ''}` });
      let failures = 0;
      provider.errorEvent.addEventListener(() => {
        if (++failures >= 2 && imageryRef.current.aerial && !viewer.isDestroyed()) {
          imageryRef.current.aerial.show = false;
          setAerialStatus('Esri World Imagery · NAIP tile fallback');
          viewer.scene.requestRender();
        }
      });
      if (imageryRef.current.aerial) viewer.imageryLayers.remove(imageryRef.current.aerial, true);
      const aerial = viewer.imageryLayers.addImageryProvider(provider, 1);
      aerial.alpha = 0;
      imageryRef.current.aerial = aerial;
      setAerialStatus(`USDA NAIP · ${data.aerial.resolution_m} m · ${data.aerial.date?.slice(0, 10)}`);
    }
  }, [data?.snapshot_id]);

  useEffect(() => {
    const viewer = viewerRef.current;
    const layer = imageryRef.current.ndvi;
    if (viewer && layer) {
      layer.show = !!selected && ndviVisible;
      layer.alpha = scenario.cloud ? .15 : .63;
      viewer.imageryLayers.raiseToTop(layer);
      viewer.scene.requestRender();
    }
  }, [selected?.id, ndviVisible, scenario.cloud, data]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.entities.values.filter(e => /^(track|grid|rejected|exclusion|drone|corridor)/.test(e.id)).forEach(e => viewer.entities.remove(e));
    missionRef.current = mission;
    if (!mission?.trace?.length) { viewer.scene.requestRender(); return; }
    const route = mission.inspection_grid;
    if (route) viewer.entities.add({ id: 'grid', polyline: { positions: C.Cartesian3.fromDegreesArrayHeights(route.coordinates.flatMap(p => [...p, 12])),
      material: new C.PolylineDashMaterialProperty({ color: amber.withAlpha(.5), dashLength: 10 }), width: 1.5 } });
    if (mission.exclusion && !application) {
      outline(viewer, 'exclusion', mission.exclusion, red, 2, 6);
      viewer.entities.add({ id: 'exclusion-fill', polygon: { hierarchy: C.Cartesian3.fromDegreesArray(ring(mission.exclusion).flat()),
        material: red.withAlpha(.25), height: 3 } });
    }
    if (mission.transit_corridor) outline(viewer, 'corridor', mission.transit_corridor, green.withAlpha(.35), 1, 5);
    mission.rejected_segments?.forEach((segment, i) => viewer.entities.add({ id: `rejected-${i}`,
      polyline: { positions: C.Cartesian3.fromDegreesArrayHeights(segment.coordinates.flatMap(p => [...p, 10])),
        material: new C.PolylineDashMaterialProperty({ color: red, dashLength: 7 }), width: 3 } }));
    const first = mission.trace[0];
    viewer.entities.add({ id: 'drone', position: C.Cartesian3.fromDegrees(...first.position, 40),
      point: { pixelSize: 10, color: green, outlineColor: color('#0E2A1B'), outlineWidth: 3, disableDepthTestDistance: Infinity },
      label: { text: application ? 'AF-1 / SIMULATED APPLICATION' : 'AF-1 / SIM', font: '12px Geist Mono', fillColor: green,
        pixelOffset: new C.Cartesian2(15, -10), horizontalOrigin: C.HorizontalOrigin.LEFT, disableDepthTestDistance: Infinity,
        showBackground: true, backgroundColor: color('#0E2A1B').withAlpha(.9) } });
    viewer.entities.add({ id: 'track', polyline: { positions: C.Cartesian3.fromDegreesArrayHeights(mission.path.slice(0, 2).flatMap(p => [...p, 40])),
      material: green, width: 2.5 } });
    const all = [...mission.path, ...ring(selected.geometry)];
    frameGround(viewer, all, 1);
    viewer.scene.requestRender();
  }, [mission?.mission_id, application]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !mission?.trace?.length) return;
    const index = Math.max(0, Math.min(mission.trace.length - 1, Math.floor((Number.isFinite(progress) ? progress : 0) * (mission.trace.length - 1))));
    const record = mission.trace[index];
    if (!record) return;
    const drone = viewer.entities.getById('drone');
    const track = viewer.entities.getById('track');
    if (drone) drone.position = new C.ConstantPositionProperty(C.Cartesian3.fromDegrees(...record.position, record.altitude_agl_m || 5));
    if (track && index > 0) track.polyline.positions = new C.ConstantProperty(C.Cartesian3.fromDegreesArrayHeights(mission.path.slice(0, index+1).flatMap(p => [...p, 40])));
    viewer.scene.requestRender();
  }, [progress, mission]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || overviewKey === 0) return;
    flightRef.current++;
    viewer.camera.flyTo({ destination: C.Cartesian3.fromDegrees(-117, 31, 11_000_000),
      duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 2,
      orientation: { heading: C.Math.toRadians(-10), pitch: C.Math.toRadians(-87), roll: 0 } });
    imageryRef.current.base.brightness = .37;
    imageryRef.current.base.saturation = .25;
    if (imageryRef.current.night) imageryRef.current.night.alpha = .7;
    if (imageryRef.current.aerial) imageryRef.current.aerial.alpha = 0;
  }, [overviewKey]);

  return <>
    <div ref={element} className="globe-canvas" aria-label="Interactive globe centered on California" />
    {error && <div className="globe-error" role="status">{error}</div>}
    <div className="imagery-credit">{selected ? <><span>AERIAL PICTURE</span> {aerialStatus}<br />Local date / resolution unverified when using World Imagery.</> : <><span>ORBIT VIEW</span> NASA VIIRS city lights, 2012 · Esri World Imagery<br />Basemap only. Observations come from Sentinel-2.</>}</div>
  </>;
}
