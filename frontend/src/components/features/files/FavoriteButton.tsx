import { useState } from 'react';
import { Star } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { fileService } from '@/services/api';

interface FavoriteButtonProps {
  fileId: string;
  isFavorite: boolean;
  size?: number;
  onSuccess?: (newFavoriteStatus: boolean) => void;
  showLabel?: boolean;
}

export function FavoriteButton({
  fileId,
  isFavorite,
  size = 20,
  onSuccess,
  showLabel = false,
}: FavoriteButtonProps) {
  const [localFavorite, setLocalFavorite] = useState(isFavorite);

  const toggleMutation = useMutation({
    mutationFn: () => fileService.toggleFavorite(fileId),
    onMutate: () => {
      // Optimistic update
      const newStatus = !localFavorite;
      setLocalFavorite(newStatus);
      onSuccess?.(newStatus);
    },
    onSuccess: (response: any) => {
      const actualStatus = response.data.is_favorite;
      setLocalFavorite(actualStatus);
      onSuccess?.(actualStatus);
    },
    onError: () => {
      // Revert on error
      setLocalFavorite(localFavorite);
    },
  });

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleMutation.mutate();
  };

  return (
    <button
      onClick={handleClick}
      disabled={toggleMutation.isPending}
      className={`transition-all duration-200 ${
        localFavorite
          ? 'text-amber-500 hover:text-amber-600'
          : 'text-slate-400 hover:text-amber-500'
      } ${toggleMutation.isPending ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      title={localFavorite ? '取消收藏' : '添加到收藏'}
    >
      <Star
        size={size}
        className={localFavorite ? 'fill-amber-500' : ''}
      />
      {showLabel && (
        <span className="ml-1 text-sm">
          {localFavorite ? '已收藏' : '收藏'}
        </span>
      )}
    </button>
  );
}
