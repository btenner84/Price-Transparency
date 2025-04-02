declare module 'react-simple-maps' {
  import React from 'react';

  export const ComposableMap: React.FC<{
    projection?: string;
    projectionConfig?: {
      scale?: number;
      center?: [number, number];
      rotate?: [number, number, number];
    };
    width?: number;
    height?: number;
    className?: string;
    style?: React.CSSProperties;
    children?: React.ReactNode;
  }>;

  export const Geographies: React.FC<{
    geography: any;
    children: (props: { geographies: any[] }) => React.ReactNode;
  }>;

  export const Geography: React.FC<{
    geography: any;
    className?: string;
    style?: {
      default?: React.CSSProperties;
      hover?: React.CSSProperties;
      pressed?: React.CSSProperties;
    };
    onClick?: (event: React.MouseEvent) => void;
  }>;
} 