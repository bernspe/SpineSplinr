from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from SpineSplinr.settings import GEN_STAFF_USER
from caserooms.models import CaseRoom, CaseRoomEntry
from users.models import User, Userrole


class CaseRoomSerializer(serializers.ModelSerializer):
    members = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.all())
    members_without_msg = serializers.SerializerMethodField('check_members_msg')
    lastmsg = serializers.SerializerMethodField('getlastmsg')
    hasssm = serializers.SerializerMethodField('check_hasssm')

    class Meta:
        model = CaseRoom
        fields = ['id','title', 'owner', 'members','created','expires','news_for_participants','members_without_msg','lastmsg','hasssm']

    def validate(self, data):
        if ~('owner' in data.keys()):
            if ('members' in data.keys()):
                req_user=self.context['request'].user
                data['members'].append(req_user)
                #check if there are children involved
                checkchild = User.objects.filter(Q(username__in=data['members']) & Q(roles__role__contains='Child')).all()
                if len(checkchild)>0:
                    if len(checkchild)==1:
                        targetuser = User.objects.filter(Q(username__in=data['members']) & Q(roles__role__contains='Caregiver')).first()
                        if ~(('title') in data.keys()):
                            data['title']=checkchild[0].get_full_name()+'\'s Rücken'
                    else:
                        raise serializers.ValidationError(
                            "Too many children specified for caseroom. Please reduce number of children.")
                else:
                    checkadult=User.objects.filter(Q(username__in=data['members']) & (Q(roles__role__contains='Adult') | Q(roles__role__contains='Patient'))).all()
                    if len(checkadult)>1:
                        raise serializers.ValidationError(
                            "Too many potential patients specified for caseroom. Please reduce number of adults or patients.")
                    if len(checkadult)==1:
                        targetuser=checkadult[0]
                        if ~(('title') in data.keys()):
                            data['title']=targetuser.get_full_name()+'\'s Rücken'
                    else:
                        targetuser = User.objects.filter(Q(username__in=data['members']) & (Q(roles__role__contains='Caregiver') | Q(roles__role__contains='Adult') | Q(roles__role__contains='Patient'))).first()
                if targetuser:
                    data['owner']=targetuser
                    data['members']= list(filter(targetuser.__ne__, data['members']))
            else:
                raise serializers.ValidationError("Potential owner not specified. Please set one member as a caregiver")

        return data

    def create(self, validated_data):
        members_data = validated_data.pop('members')
        cr = CaseRoom.objects.create(**validated_data)
        for m in members_data:
            if (cr.owner != m):
                cr.members.add(m)
                cr.news_for_participants.add(m)
        cr.save()
        return cr

    def check_members_msg(self,cr):
        m_wo_msg=[]
        for m in cr.members.all():
            cre=CaseRoomEntry.objects.filter(caseroom=cr, sender=m).all()
            if len(cre)==0:
                m_wo_msg.append(m.username)
        return m_wo_msg

    def getlastmsg(self, cr):
        lm=cr.get_last_msg()
        if lm:
            serializer = CaseRoomEntrySerializer(lm, many=False)
            return serializer.data
        else:
            return None

    def check_hasssm(self,cr):
        u=cr.get_members_and_owners_with_active_SSM()
        if u:
            return True
        else:
            return False


class CaseRoomEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseRoomEntry
        fields = '__all__'

    def validate(self,data):
        cr = data['caseroom']
        participants=cr.get_members_and_owner_str().split(',')
        sender=data['sender']
        if (str(sender) in participants):
            return data
        else:
            if (sender.is_staff):
                cr.members.add(sender)
                return data
            else:
                raise serializers.ValidationError("Sender not in Caseroom participants")


    def create(self, validated_data):
        cre = CaseRoomEntry.objects.create(**validated_data)
        cre.save()
        sender = validated_data.pop('sender')
        cr = cre.caseroom  #caseroom instance
        try:
            # get cr participants without the message sender
            participants=list(filter((str(sender)).__ne__, cr.get_members_and_owner_str().split(',')))
            # in case the sender is staff member -> remove the staff tag
            if ((sender.is_staff) & (GEN_STAFF_USER['username'] in participants)):
                participants.remove(GEN_STAFF_USER['username'])
            # add info tag for new messages in caseroom instance
            for p in participants:
                cr.news_for_participants.add(p)
               # cr.email_reminder_for_participants.add(p)
        except:
            pass
        return cre