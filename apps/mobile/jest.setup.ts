jest.mock("@maplibre/maplibre-react-native", () => {
  const React = jest.requireActual<typeof import("react")>("react");

  function FrozenId({
    id,
    children,
  }: {
    id: string;
    children?: React.ReactNode;
  }) {
    const originalId = React.useRef(id);
    if (originalId.current !== id) throw new Error("`id` cannot be changed");
    return React.createElement(React.Fragment, null, children);
  }

  function StableMap({
    children,
    light,
  }: {
    children?: React.ReactNode;
    light?: object;
  }) {
    const previouslyHadLight = React.useRef(light !== undefined);
    if (previouslyHadLight.current && light === undefined) {
      throw new Error("Map light must remain an object across display modes");
    }
    previouslyHadLight.current = light !== undefined;
    return React.createElement(React.Fragment, null, children);
  }

  return {
    Camera: () => null,
    GeoJSONSource: FrozenId,
    Layer: FrozenId,
    Map: StableMap,
    Marker: FrozenId,
  };
});
