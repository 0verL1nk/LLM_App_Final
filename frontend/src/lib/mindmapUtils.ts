import type { Node, Edge } from '@xyflow/react';

export function transformMindmapData(data: any): { nodes: Node[]; edges: Edge[] } {
  // Mock transformation logic
  // Expecting data format: { id, label, children: [...] }
  
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  
  const processNode = (item: any, x: number, y: number, parentId?: string) => {
    const nodeId = item.id || `node-${Math.random().toString(36).substr(2, 9)}`;
    
    nodes.push({
      id: nodeId,
      data: { label: item.label || item.text || '节点' },
      position: { x, y },
      type: 'default',
      style: {
        background: parentId ? '#fff' : '#4f46e5',
        color: parentId ? '#333' : '#fff',
        border: '1px solid #e2e8f0',
        borderRadius: '8px',
        fontSize: parentId ? '12px' : '14px',
        fontWeight: parentId ? 'normal' : 'bold',
        padding: '10px',
        width: 150,
      }
    });
    
    if (parentId) {
      edges.push({
        id: `e-${parentId}-${nodeId}`,
        source: parentId,
        target: nodeId,
        animated: true,
      });
    }
    
    if (item.children && item.children.length > 0) {
      item.children.forEach((child: any, index: number) => {
        processNode(child, x + 250, y + (index - (item.children.length - 1) / 2) * 100, nodeId);
      });
    }
  };
  
  if (data) {
    processNode(data, 50, 200);
  }
  
  return { nodes, edges };
}
