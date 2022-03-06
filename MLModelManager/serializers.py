from rest_framework import serializers

from MLModelManager.models import MLModel, MLFile

class MLFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLFile
        fields = '__all__'

class MLModelSerializer(serializers.ModelSerializer):
    files = MLFileSerializer(source='mlfile_set',many=True, read_only=True)
    owner_fullname = serializers.ReadOnlyField(source='owner.get_full_name')

    class Meta:
        model = MLModel
        fields = '__all__'

    def update(self, instance, validated_data):
        file_data=[]
        try:
            file_data = validated_data.pop('files')
        except:
            pass

        for f in file_data.values():
            fileObj=MLFile.objects.filter(mlmodel=instance,file__endswith=f.name).first()
            fileObj.file=f
            fileObj.save()
            #MLFile.objects.create(mlmodel=instance, file=f)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        file_data=[]
        try:
            file_data = validated_data.pop('files')
        except:
            pass
        mlmodel = MLModel.objects.create(**validated_data)
        for f in file_data.values():
            MLFile.objects.create(mlmodel=mlmodel, file=f)
        return mlmodel

