import FeaturePlaceholder from "../../components/FeaturePlaceholder";


export default function InventoryPlaceholderPage({ title, subtitle, note, items }) {
  return (
    <FeaturePlaceholder
      title={title}
      subtitle={subtitle}
      items={items}
      note={note}
    />
  );
}
